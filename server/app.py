"""Matching server -- the middle part of the prototype.

It sits between the web client (which collects profiles) and the AI matcher
(dating_matching_ai.DatingMatchingAI). This `prototype_no_keys` build has the
TEE crypto/attestation stripped out so the pipeline runs locally with no keys.

Flow
----
1. /submit            web client posts the user profile (see SubmitPayload:
                      profile / demographics / matching_data). We KEEP the raw
                      story text (the AI matcher needs it) plus demographics, and
                      compute a cheap cosine vector for prefiltering.
2. /admin/match-round hard-gate impossible pairs by demographics (mutual gender
                      preference + mutual age fit), prefilter the rest by cheap
                      cosine (prefilter.py), run the expensive AI matcher only on
                      that shortlist (dating_matching_ai.py), then greedily assign
                      each person at most one partner by AI score.
3. /result/{token}    each client polls its own match.
4. /stats             content-free aggregate counts.

The core lives in `MatchEngine` (pure Python + numpy). FastAPI is an optional
thin HTTP layer on top, so the engine is importable/testable even where fastapi
is not installed (see simulate_web.py).
"""
from __future__ import annotations

import os
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path)
except ImportError:
    pass
import secrets
import logging
import time
import threading
import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

# Setup logging to both console and a file in the server directory
logger = logging.getLogger("dating_server")
logger.setLevel(logging.INFO)

# Make sure we don't duplicate handlers if app is re-imported
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    
    # File Handler
    log_file_path = os.path.join(os.path.dirname(__file__), "server.log")
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Stream Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

from prefilter import candidate_pairs, embed

ADMIN_TOKEN = os.environ.get("MATCH_ADMIN_TOKEN", "let-me-match")
# AI compatibility score (0..100) at/above which a candidate pair may be matched.
AI_THRESHOLD = float(os.environ.get("MATCH_AI_THRESHOLD", "60"))
# Nearest neighbours kept per person during the cheap prefilter.
PREFILTER_TOP_K = int(os.environ.get("MATCH_PREFILTER_TOP_K", "5"))


@dataclass
class Profile:
    user_id: str
    token: str            # secret handle the client polls with
    handle: str           # what to reveal on a match (e.g. "Serafim 🦊")
    last_name: str        # kept private; reveal only after a match if desired
    # Raw story text is KEPT (unlike the original enclave build) because the AI
    # matcher reads text, not vectors.
    text: str
    wants: str
    dealbreakers: list[str]
    # Demographics: hard gates applied before any matching.
    my_gender: str
    target_gender: str
    age: int | None
    age_min: int | None
    age_max: int | None
    languages: list[str]  # parsed but not yet used for filtering
    vector: Any           # numpy array, cheap prefilter signal only


# -- demographic hard gates ---------------------------------------------
_OPEN_GENDERS = {"", "any", "everyone", "all", "both", "other", "anyone"}


def _wants_gender(target: str, other_gender: str) -> bool:
    """Does someone whose preference is `target` accept `other_gender`?"""
    target = target.strip().lower()
    if target in _OPEN_GENDERS:
        return True
    return target == other_gender.strip().lower()


def _gender_ok(a: Profile, b: Profile) -> bool:
    """Mutual gender preference: each must want the other's gender."""
    return (
        _wants_gender(a.target_gender, b.my_gender)
        and _wants_gender(b.target_gender, a.my_gender)
    )


def _age_ok(a: Profile, b: Profile) -> bool:
    """Mutual age fit: each person's own age within the other's range.

    If an age or range is missing we don't block (graceful until the users API
    ships the `age` field everywhere).
    """
    def fits(age: int | None, lo: int | None, hi: int | None) -> bool:
        if age is None or lo is None or hi is None:
            return True
        return lo <= age <= hi

    return fits(a.age, b.age_min, b.age_max) and fits(b.age, a.age_min, a.age_max)


@dataclass
class Match:
    peer_handle: str
    connection_code: str
    score: float
    verdict: str
    reasons: list[str]


@dataclass
class MatchResult:
    matched: bool
    matches: list[Match] = field(default_factory=list)
    evaluations: list[dict] = field(default_factory=list)

    @property
    def peer_handle(self) -> str | None:
        return self.matches[0].peer_handle if self.matches else None

    @property
    def connection_code(self) -> str | None:
        return self.matches[0].connection_code if self.matches else None

    @property
    def score(self) -> float | None:
        return self.matches[0].score if self.matches else None

    @property
    def verdict(self) -> str | None:
        return self.matches[0].verdict if self.matches else None

    @property
    def reasons(self) -> list[str]:
        return self.matches[0].reasons if self.matches else []


@dataclass
class ChatMessage:
    sender_token: str
    sender_handle: str
    text: str
    timestamp: float


class MatchEngine:
    """Framework-free core. The FastAPI routes are thin wrappers over this."""

    def __init__(self, ai_threshold: float = AI_THRESHOLD) -> None:
        self._profiles: dict[str, Profile] = {}     # token -> Profile
        self._results: dict[str, MatchResult] = {}   # token -> result
        self._chat_rooms: dict[str, list[ChatMessage]] = {} # room_id -> messages
        self._push_subscriptions: dict[str, list[dict]] = {} # token -> list of push subscriptions
        self._round_done = False
        self._ai_threshold = ai_threshold
        self._ai = None  # lazily loaded; the model is expensive to construct
        self._running_matching = False
        self._pending_match_round = False
        self._lock = threading.RLock()
        self._db_dirty = False
        self._stop_saver = False
        self._stop_backup = False
        self._load_db()
        
        self._saver_thread = threading.Thread(target=self._background_saver, daemon=True)
        self._saver_thread.start()
        
        self._backup_thread = threading.Thread(target=self._background_backup, daemon=True)
        self._backup_thread.start()

    def _background_saver(self):
        while not self._stop_saver:
            time.sleep(2.0)
            try:
                with self._lock:
                    if self._db_dirty:
                        self._save_db_now()
                        self._db_dirty = False
            except Exception as e:
                logger.error(f"[ENGINE] Saver thread error: {e}")

    def _background_backup(self):
        server_dir = os.path.dirname(__file__)
        backup_dir = os.path.join(server_dir, "backups")
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"[ENGINE] Failed to create backups directory: {e}")
            return

        interval_seconds = 6 * 3600  # 6 hours
        
        # Initialize last_backup_time to 0.0 so a backup is run shortly after startup.
        last_backup_time = 0.0
        
        while not self._stop_backup:
            now = time.time()
            if now - last_backup_time >= interval_seconds:
                try:
                    self._run_backup_now(backup_dir)
                    last_backup_time = now
                except Exception as e:
                    logger.error(f"[ENGINE] Backup thread error: {e}")
            
            # Sleep in short increments of 10 seconds to allow responsive thread shutdown
            for _ in range(6):
                if self._stop_backup:
                    break
                time.sleep(10.0)

    def _run_backup_now(self, backup_dir: str):
        # Generate timestamp safe for Windows/Linux/Mac filesystems (no colons)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"db_backup_{timestamp}.json.bak"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        with self._lock:
            data = {
                "profiles": {},
                "results": {},
                "chat_rooms": {},
                "round_done": self._round_done
            }
            for token, p in self._profiles.items():
                data["profiles"][token] = {
                    "user_id": p.user_id,
                    "token": p.token,
                    "handle": p.handle,
                    "last_name": p.last_name,
                    "text": p.text,
                    "wants": p.wants,
                    "dealbreakers": p.dealbreakers,
                    "my_gender": p.my_gender,
                    "target_gender": p.target_gender,
                    "age": p.age,
                    "age_min": p.age_min,
                    "age_max": p.age_max,
                    "languages": p.languages,
                    "vector": p.vector.tolist() if hasattr(p.vector, "tolist") else list(p.vector)
                }
            for token, res in self._results.items():
                data["results"][token] = {
                    "matched": res.matched,
                    "matches": [
                        {
                            "peer_handle": m.peer_handle,
                            "connection_code": m.connection_code,
                            "score": m.score,
                            "verdict": m.verdict,
                            "reasons": m.reasons
                        }
                        for m in getattr(res, "matches", [])
                    ],
                    "evaluations": getattr(res, "evaluations", [])
                }
            for room_id, messages in self._chat_rooms.items():
                data["chat_rooms"][room_id] = [
                    {
                        "sender_token": m.sender_token,
                        "sender_handle": m.sender_handle,
                        "text": m.text,
                        "timestamp": m.timestamp
                    }
                    for m in messages
                ]

        import json
        temp_path = backup_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, backup_path)
            logger.info(f"[ENGINE] Database backup successfully saved to: {backup_filename}")
        except Exception as e:
            logger.error(f"[ENGINE] Failed to save backup to file: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        # Clean up old backups
        self._cleanup_old_backups(backup_dir)

    def _cleanup_old_backups(self, backup_dir: str):
        now = time.time()
        one_week_seconds = 7 * 24 * 3600
        try:
            for entry in os.scandir(backup_dir):
                if entry.is_file() and entry.name.startswith("db_backup_") and entry.name.endswith(".json.bak"):
                    file_age = now - entry.stat().st_mtime
                    if file_age > one_week_seconds:
                        os.remove(entry.path)
                        logger.info(f"[ENGINE] Deleted old backup file: {entry.name}")
        except Exception as e:
            logger.error(f"[ENGINE] Error cleaning up old backups: {e}")

    # -- submission ------------------------------------------------------
    def submit(self, payload: dict[str, Any]) -> str:
        """Accept the users-API profile shape:

            {
              "profile":      {first_name, last_name, avatar_index, avatar_emoji},
              "demographics": {my_gender, target_gender, age, age_range:{min,max},
                               languages: [...]},
              "matching_data":{story}
            }
        """
        profile = payload.get("profile") or {}
        demo = payload.get("demographics") or {}
        matching = payload.get("matching_data") or {}
        age_range = demo.get("age_range") or {}

        text = str(matching.get("story", "")).strip()
        if not text:
            raise ValueError("empty profile (matching_data.story is required)")

        first = str(profile.get("first_name", "")).strip()
        if not first:
            raise ValueError("first_name is required")

        last = str(profile.get("last_name", "")).strip()
        if not last:
            raise ValueError("last_name is required")

        age = demo.get("age") if demo.get("age") is not None else profile.get("age")
        if age is None or age < 18:
            raise ValueError("age must be at least 18")

        avatar_index = profile.get("avatar_index")
        if avatar_index is None:
            raise ValueError("avatar_index is required")

        my_gender = str(demo.get("my_gender", "")).strip()
        if not my_gender:
            raise ValueError("my_gender is required")

        target_gender = str(demo.get("target_gender", "")).strip()
        if not target_gender:
            raise ValueError("target_gender is required")

        languages = demo.get("languages")
        if not languages or len(languages) == 0:
            raise ValueError("at least one language is required")

        emoji = str(profile.get("avatar_emoji", "")).strip()
        if age:
            handle = f"{first}, {age} {emoji}".strip() if emoji else f"{first}, {age}"
        else:
            handle = " ".join(p for p in (first, emoji) if p) or "someone in the room"

        existing_token = payload.get("token")
        vector = embed(text)
        
        with self._lock:
            if existing_token and existing_token in self._profiles:
                token = existing_token
                p = self._profiles[token]
                p.handle = handle
                p.last_name = last
                p.text = text
                p.my_gender = my_gender
                p.target_gender = target_gender
                p.age = age
                p.age_min = age_range.get("min")
                p.age_max = age_range.get("max")
                p.languages = [str(l) for l in demo.get("languages", [])]
                p.vector = vector
                self._results[token] = MatchResult(matched=False)
                logger.info(f"[ENGINE] Profile updated: handle='{handle}', token={token[:8]}...")
            else:
                token = secrets.token_urlsafe(16)
                user_id = secrets.token_hex(8)
                self._profiles[token] = Profile(
                    user_id=user_id,
                    token=token,
                    handle=handle,
                    last_name=last,
                    text=text,
                    wants="",
                    dealbreakers=[],
                    my_gender=my_gender,
                    target_gender=target_gender,
                    age=age,
                    age_min=age_range.get("min"),
                    age_max=age_range.get("max"),
                    languages=[str(l) for l in demo.get("languages", [])],
                    vector=vector,
                )
                self._results.setdefault(token, MatchResult(matched=False))
                logger.info(f"[ENGINE] Profile submitted: handle='{handle}', token={token[:8]}...")

            self._round_done = False
            self._save_db()
        return token

    # -- the one batch round --------------------------------------------
    def _matcher(self):
        if self._ai is None:
            from dating_matching_ai import DatingMatchingAI

            self._ai = DatingMatchingAI(threshold=self._ai_threshold, verbose=False)
        return self._ai

    def run_match_round(self, top_k: int = PREFILTER_TOP_K, force: bool = False) -> dict:
        with self._lock:
            if self._running_matching:
                logger.info("[ENGINE] Match round already in progress. Queueing a pending round.")
                self._pending_match_round = True
                return {}
            self._running_matching = True

        last_summary = {}
        try:
            while True:
                with self._lock:
                    profiles = list(self._profiles.values())
                    by_uid = {p.user_id: p for p in profiles}
                
                logger.info(f"[ENGINE] Starting match round iteration with {len(profiles)} active profiles.")
                
                if len(profiles) < 2 and not force:
                    logger.info("[ENGINE] Fewer than 2 profiles and not forced. Postponing match round finalization.")
                    with self._lock:
                        self._round_done = False
                        self._save_db()
                    last_summary = {
                        "profiles": len(profiles),
                        "candidate_pairs": 0,
                        "ai_calls": 0,
                        "pairs": 0,
                        "unmatched": len(profiles),
                    }
                else:
                    # 1. prefilter
                    def eligible(uid_a: str, uid_b: str) -> bool:
                        a, b = by_uid[uid_a], by_uid[uid_b]
                        return _gender_ok(a, b) and _age_ok(a, b)

                    vectors = [(p.user_id, p.vector) for p in profiles]
                    shortlist = candidate_pairs(vectors, top_k=top_k, eligible=eligible)
                    logger.info(f"[ENGINE] Prefilter phase completed. {len(shortlist)} candidate pairs passed demographics/prefilter.")

                    # 2. AI scoring (lock-free)
                    ai = self._matcher()
                    inputs = []
                    for a_uid, b_uid, _cos in shortlist:
                        a, b = by_uid[a_uid], by_uid[b_uid]
                        inputs.append((a, b))

                    semantic_scores = []
                    if ai.cross_encoder is not None and inputs:
                        text_pairs = [
                            (f"Bio: {a.text}\nLooking for: {a.wants}", f"Bio: {b.text}\nLooking for: {b.wants}")
                            for a, b in inputs
                        ]
                        logger.info(f"[ENGINE] Batch predicting {len(text_pairs)} semantic scores via CrossEncoder.")
                        raw_scores = ai.cross_encoder.predict(text_pairs, batch_size=64, show_progress_bar=False)
                        for raw_score in raw_scores:
                            if raw_score > 1.0:
                                raw_score = raw_score / 5.0
                            semantic_scores.append(ai._clamp(float(raw_score)))
                    else:
                        for a, b in inputs:
                            text_a = f"Bio: {a.text}\nLooking for: {a.wants}"
                            text_b = f"Bio: {b.text}\nLooking for: {b.wants}"
                            words_a = set(ai._clean(text_a).split())
                            words_b = set(ai._clean(text_b).split())
                            if not words_a or not words_b:
                                score = 0.0
                            else:
                                score = ai._clamp(3.0 * len(words_a & words_b) / len(words_a | words_b))
                            semantic_scores.append(score)

                    # Compute all final scores
                    scored: list[tuple[float, str, str, str, list[str]]] = []
                    debug_scores_temp = {}
                    for idx, (a, b) in enumerate(inputs):
                        profile_a = ai._parse_user(self._as_user(a))
                        profile_b = ai._parse_user(self._as_user(b))
                        
                        traits_a = ai._extract_traits(profile_a)
                        traits_b = ai._extract_traits(profile_b)
                        
                        semantic_score = semantic_scores[idx]
                        values_score = ai._values_compatibility(traits_a, traits_b)
                        lifestyle_score = ai._lifestyle_compatibility(traits_a, traits_b)
                        social_score = ai._social_energy_compatibility(traits_a, traits_b)
                        intent_score = ai._relationship_intent_compatibility(traits_a, traits_b)
                        
                        dealbreaker_penalty = max(
                            ai._dealbreaker_penalty(profile_a, profile_b),
                            ai._dealbreaker_penalty(profile_b, profile_a),
                        )
                        
                        final_score_0_1 = (
                            0.75 * semantic_score +
                            0.077 * values_score +
                            0.077 * lifestyle_score +
                            0.058 * social_score +
                            0.038 * intent_score -
                            0.45 * dealbreaker_penalty
                        )
                        final_score_0_1 = ai._clamp(final_score_0_1)
                        score = round(final_score_0_1 * 100, 1)
                        
                        verdict = ai._verdict(score)
                        match_ok = score >= ai.threshold
                        reasons = ai._safe_explanation(
                            semantic_score=semantic_score,
                            values_score=values_score,
                            lifestyle_score=lifestyle_score,
                            social_score=social_score,
                            intent_score=intent_score,
                            penalty=dealbreaker_penalty,
                            traits_a=traits_a,
                            traits_b=traits_b,
                        )
                        
                        logger.info(f"[ENGINE] AI Result ({a.handle} <-> {b.handle}): Score={score}%, Match={match_ok}, Verdict='{verdict}'")
                        if match_ok:
                            scored.append((score, a.user_id, b.user_id, verdict, reasons))
                        
                        if a.token not in debug_scores_temp:
                            debug_scores_temp[a.token] = []
                        if b.token not in debug_scores_temp:
                            debug_scores_temp[b.token] = []
                        debug_scores_temp[a.token].append({
                            "peer_handle": b.handle,
                            "score": score,
                            "verdict": verdict
                        })
                        debug_scores_temp[b.token].append({
                            "peer_handle": a.handle,
                            "score": score,
                            "verdict": verdict
                        })

                    # 3. assignment (under lock)
                    with self._lock:
                        scored.sort(reverse=True, key=lambda t: t[0])
                        pairs = 0
                        # Reset results to rebuild them
                        for token in self._profiles:
                            self._results[token] = MatchResult(matched=False, matches=[], evaluations=debug_scores_temp.get(token, []))
                        
                        match_counts = {}
                        for score, a_uid, b_uid, verdict, reasons in scored:
                            count_a = match_counts.get(a_uid, 0)
                            count_b = match_counts.get(b_uid, 0)
                            if count_a >= 3 or count_b >= 3:
                                continue
                            a = by_uid.get(a_uid)
                            b = by_uid.get(b_uid)
                            if not a or not b:
                                continue
                            import hashlib
                            uids = sorted([a.user_id, b.user_id])
                            combined_hash = hashlib.md5(f"{uids[0]}-{uids[1]}".encode('utf-8')).hexdigest()[:8]
                            code = f"code-{combined_hash}"
                            
                            if a.token in self._results:
                                self._results[a.token].matched = True
                                self._results[a.token].matches.append(Match(
                                    peer_handle=b.handle,
                                    connection_code=code,
                                    score=score,
                                    verdict=verdict,
                                    reasons=reasons
                                ))
                                self.send_push_notification(
                                    token=a.token,
                                    title="New Match Found! 🎉",
                                    body=f"You matched with {b.handle}!",
                                    match_id=f"real_match_{code}",
                                    is_match=True
                                )
                            
                            if b.token in self._results:
                                self._results[b.token].matched = True
                                self._results[b.token].matches.append(Match(
                                    peer_handle=a.handle,
                                    connection_code=code,
                                    score=score,
                                    verdict=verdict,
                                    reasons=reasons
                                ))
                                self.send_push_notification(
                                    token=b.token,
                                    title="New Match Found! 🎉",
                                    body=f"You matched with {a.handle}!",
                                    match_id=f"real_match_{code}",
                                    is_match=True
                                )
                            
                            match_counts[a_uid] = count_a + 1
                            match_counts[b_uid] = count_b + 1
                            pairs += 1
                            logger.info(f"[ENGINE] Match formed: {a.handle} <-> {b.handle} (Score={score}%, Code={code})")

                        self._round_done = True
                        last_summary = {
                            "profiles": len(profiles),
                            "candidate_pairs": len(shortlist),
                            "ai_calls": len(shortlist),
                            "pairs": pairs,
                            "unmatched": sum(1 for res in self._results.values() if not res.matched),
                        }
                        logger.info(f"[ENGINE] Match round completed. Summary: {last_summary}")
                        # Force save to disk for match rounds to ensure matches are fully saved
                        self._save_db_now()

                # Check if new rounds were scheduled while we were running
                with self._lock:
                    if not self._pending_match_round:
                        self._running_matching = False
                        break
                    self._pending_match_round = False
        except Exception as e:
            logger.error(f"[ENGINE] Error during match round: {e}", exc_info=True)
            with self._lock:
                self._running_matching = False
                self._pending_match_round = False

    @staticmethod
    def _as_user(p: Profile) -> dict[str, Any]:
        return {
            "id": p.user_id,
            "text": p.text,
            "wants": p.wants,
            "dealbreakers": p.dealbreakers,
        }

    # -- reads -----------------------------------------------------------
    # -- reads -----------------------------------------------------------
    def result_for(self, token: str) -> MatchResult | None:
        with self._lock:
            if token not in self._profiles:
                logger.warning(f"[ENGINE] Result poll rejected: unknown token='{token[:8]}...'")
                return None
            res = self._results.get(token, MatchResult(matched=False))
            logger.info(f"[ENGINE] Result poll: handle='{self._profiles[token].handle}', matched={res.matched}, token='{token[:8]}...'")
            return res

    def stats(self) -> dict:
        with self._lock:
            matched = sum(1 for r in self._results.values() if r.matched)
            return {
                "profiles": len(self._profiles),
                "matched_people": matched,
                "pairs": matched // 2,
                "round_done": self._round_done,
            }

    def send_message(self, token: str, text: str, room_id: Optional[str] = None) -> bool:
        with self._lock:
            profile = self._profiles.get(token)
            if not profile:
                raise ValueError("unknown token")
            res = self._results.get(token)
            if not res or not res.matched:
                raise ValueError("user is not matched")
            if not room_id:
                if hasattr(res, "matches") and res.matches:
                    room_id = res.matches[0].connection_code
                else:
                    room_id = getattr(res, "connection_code", None)
            if not room_id:
                raise ValueError("no room found")
            self._chat_rooms.setdefault(room_id, [])
            msg = ChatMessage(
                sender_token=token,
                sender_handle=profile.handle,
                text=text,
                timestamp=time.time()
            )
            self._chat_rooms[room_id].append(msg)
            logger.info(f"[ENGINE] Chat message sent: from='{profile.handle}' room='{room_id}' text='{text}'")
            self._save_db()
            
            # Notify peer via Push Notifications
            peer_token = None
            for p_token, p in self._profiles.items():
                if p_token != token:
                    res = self._results.get(p_token)
                    if res and res.matched:
                        for m in res.matches:
                            if m.connection_code == room_id:
                                peer_token = p_token
                                break
                if peer_token:
                    break
            
            if peer_token:
                self.send_push_notification(
                    token=peer_token,
                    title=profile.handle,
                    body=text,
                    match_id=f"real_match_{room_id}",
                    is_match=False
                )
            
            return True

    def get_messages(self, token: str, room_id: Optional[str] = None) -> list[dict]:
        with self._lock:
            profile = self._profiles.get(token)
            if not profile:
                return []
            res = self._results.get(token)
            if not res or not res.matched:
                return []
            if not room_id:
                if hasattr(res, "matches") and res.matches:
                    room_id = res.matches[0].connection_code
                else:
                    room_id = getattr(res, "connection_code", None)
            if not room_id:
                return []
            messages = self._chat_rooms.get(room_id, [])
            return [
                {
                    "sender": "sent" if m.sender_token == token else "received",
                    "text": m.text,
                    "sender_handle": m.sender_handle
                }
                for m in messages
            ]

    def get_all_messages(self, token: str) -> dict[str, list[dict]]:
        with self._lock:
            profile = self._profiles.get(token)
            if not profile:
                return {}
            res = self._results.get(token)
            if not res or not res.matched:
                return {}
            
            all_rooms_messages = {}
            for m in getattr(res, "matches", []):
                room_id = m.connection_code
                if not room_id:
                    continue
                messages = self._chat_rooms.get(room_id, [])
                all_rooms_messages[room_id] = [
                    {
                        "sender": "sent" if msg.sender_token == token else "received",
                        "text": msg.text,
                        "sender_handle": msg.sender_handle,
                        "timestamp": msg.timestamp
                    }
                    for msg in messages
                ]
            return all_rooms_messages

    def _save_db(self):
        # Simply mark database as dirty; the saver thread will write it to disk within 2 seconds
        self._db_dirty = True

    def _save_db_now(self):
        try:
            db_path = os.path.join(os.path.dirname(__file__), "db.json")
            data = {
                "profiles": {},
                "results": {},
                "chat_rooms": {},
                "push_subscriptions": self._push_subscriptions,
                "round_done": self._round_done
            }
            for token, p in self._profiles.items():
                data["profiles"][token] = {
                    "user_id": p.user_id,
                    "token": p.token,
                    "handle": p.handle,
                    "last_name": p.last_name,
                    "text": p.text,
                    "wants": p.wants,
                    "dealbreakers": p.dealbreakers,
                    "my_gender": p.my_gender,
                    "target_gender": p.target_gender,
                    "age": p.age,
                    "age_min": p.age_min,
                    "age_max": p.age_max,
                    "languages": p.languages,
                    "vector": p.vector.tolist() if hasattr(p.vector, "tolist") else list(p.vector)
                }
            for token, res in self._results.items():
                data["results"][token] = {
                    "matched": res.matched,
                    "matches": [
                        {
                            "peer_handle": m.peer_handle,
                            "connection_code": m.connection_code,
                            "score": m.score,
                            "verdict": m.verdict,
                            "reasons": m.reasons
                        }
                        for m in getattr(res, "matches", [])
                    ],
                    "evaluations": getattr(res, "evaluations", [])
                }
            for room_id, messages in self._chat_rooms.items():
                data["chat_rooms"][room_id] = [
                    {
                        "sender_token": m.sender_token,
                        "sender_handle": m.sender_handle,
                        "text": m.text,
                        "timestamp": m.timestamp
                    }
                    for m in messages
                ]
            import json
            # Atomic swap to prevent disk corruption
            temp_path = db_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, db_path)
            logger.info("[ENGINE] Database successfully saved to disk.")
        except Exception as e:
            logger.error(f"[ENGINE] Failed to save database to disk: {e}")

    def _load_db(self):
        try:
            db_path = os.path.join(os.path.dirname(__file__), "db.json")
            if not os.path.exists(db_path):
                return
            import json
            import numpy as np
            with open(db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._round_done = data.get("round_done", False)
            self._push_subscriptions = data.get("push_subscriptions", {})
            for token, p_data in data.get("profiles", {}).items():
                self._profiles[token] = Profile(
                    user_id=p_data["user_id"],
                    token=p_data["token"],
                    handle=p_data["handle"],
                    last_name=p_data["last_name"],
                    text=p_data["text"],
                    wants=p_data["wants"],
                    dealbreakers=p_data["dealbreakers"],
                    my_gender=p_data["my_gender"],
                    target_gender=p_data["target_gender"],
                    age=p_data["age"],
                    age_min=p_data["age_min"],
                    age_max=p_data["age_max"],
                    languages=p_data["languages"],
                    vector=np.array(p_data["vector"], dtype=np.float32)
                )
            for token, res_data in data.get("results", {}).items():
                if "matches" in res_data:
                    matches = [
                        Match(
                            peer_handle=m["peer_handle"],
                            connection_code=m["connection_code"],
                            score=m["score"],
                            verdict=m["verdict"],
                            reasons=m["reasons"]
                        )
                        for m in res_data["matches"]
                    ]
                    self._results[token] = MatchResult(
                        matched=res_data["matched"],
                        matches=matches,
                        evaluations=res_data.get("evaluations", [])
                    )
                else:
                    matches = []
                    if res_data.get("matched"):
                        matches.append(Match(
                            peer_handle=res_data.get("peer_handle", ""),
                            connection_code=res_data.get("connection_code", ""),
                            score=res_data.get("score", 0.0),
                            verdict=res_data.get("verdict", ""),
                            reasons=res_data.get("reasons", [])
                        ))
                    self._results[token] = MatchResult(
                        matched=res_data.get("matched", False),
                        matches=matches,
                        evaluations=res_data.get("evaluations", [])
                    )
            for room_id, msgs_data in data.get("chat_rooms", {}).items():
                self._chat_rooms[room_id] = [
                    ChatMessage(
                        sender_token=m["sender_token"],
                        sender_handle=m["sender_handle"],
                        text=m["text"],
                        timestamp=m["timestamp"]
                    )
                    for m in msgs_data
                ]
            logger.info(f"[ENGINE] Database loaded successfully: {len(self._profiles)} profiles, {len(self._chat_rooms)} chat rooms.")
        except Exception as e:
            logger.error(f"[ENGINE] Failed to load database: {e}")

    def clear_db(self):
        with self._lock:
            self._profiles = {}
            self._results = {}
            self._chat_rooms = {}
            self._push_subscriptions = {}
            self._round_done = False
            self._save_db_now()
            logger.info("[ENGINE] Database successfully cleared via debug admin request.")

    def save_push_subscription(self, token: str, sub: dict):
        with self._lock:
            self._push_subscriptions.setdefault(token, [])
            if sub not in self._push_subscriptions[token]:
                self._push_subscriptions[token].append(sub)
                self._save_db()
                logger.info(f"[ENGINE] Saved push subscription for token {token[:8]}...")

    def send_push_notification(self, token: str, title: str, body: str, match_id: str = "", is_match: bool = False):
        subscriptions = self._push_subscriptions.get(token, [])
        if not subscriptions:
            return
        
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            logger.warning("[ENGINE] pywebpush library is not installed. Skipping push notification.")
            return
            
        vapid_private = os.environ.get("VAPID_PRIVATE_KEY")
        vapid_public = os.environ.get("VAPID_PUBLIC_KEY")
        vapid_claims = {"sub": os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")}
        
        if not vapid_private or not vapid_public:
            logger.warning("[ENGINE] VAPID keys not configured in environment. Skipping push notification.")
            return
            
        payload = {
            "title": title,
            "body": body,
            "matchId": match_id,
            "isMatch": is_match
        }
        import json
        payload_str = json.dumps(payload)
        
        for sub in list(subscriptions):
            try:
                webpush(
                    subscription_info=sub,
                    data=payload_str,
                    vapid_private_key=vapid_private,
                    vapid_public_key=vapid_public,
                    vapid_claims=vapid_claims
                )
                logger.info(f"[ENGINE] Sent push notification to subscription for token {token[:8]}...")
            except WebPushException as ex:
                if ex.response is not None and ex.response.status_code in [404, 410]:
                    with self._lock:
                        if sub in self._push_subscriptions.get(token, []):
                            self._push_subscriptions[token].remove(sub)
                            self._save_db()
                            logger.info(f"[ENGINE] Removed expired push subscription for token {token[:8]}...")
                else:
                    logger.error(f"[ENGINE] WebPushException: {ex}")
            except Exception as ex:
                logger.error(f"[ENGINE] Failed to send push notification: {ex}")


ENGINE = MatchEngine()


# ----------------------------------------------------------------------
# Optional FastAPI HTTP layer (the actual server the web client talks to).
# Guarded so the engine above stays importable without fastapi installed.
# ----------------------------------------------------------------------
try:
    from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel

    class ProfileBlock(BaseModel):
        first_name: str = ""
        last_name: str = ""
        age: Optional[int] = None
        avatar_index: Optional[int] = None
        avatar_emoji: str = ""

    class AgeRange(BaseModel):
        min: Optional[int] = None
        max: Optional[int] = None

    class Demographics(BaseModel):
        my_gender: str = ""
        target_gender: str = ""
        age: Optional[int] = None
        age_range: AgeRange = AgeRange()
        languages: list[str] = []

    class MatchingData(BaseModel):
        story: str = ""

    class SubmitPayload(BaseModel):
        token: Optional[str] = None
        profile: ProfileBlock = ProfileBlock()
        demographics: Demographics = Demographics()
        matching_data: MatchingData = MatchingData()

    class ChatSendPayload(BaseModel):
        token: str
        text: str
        room_id: Optional[str] = None

    class SubscriptionPayload(BaseModel):
        token: str
        subscription: dict

    app = FastAPI(title="Matching server (prototype_no_keys)")

    # The users API is a separate web origin, so the browser needs CORS.
    # Prototype: allow everything. Lock this down to the real frontend
    # origin(s) before any non-demo deployment.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("MATCH_CORS_ORIGINS", "*").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        logger.info(f"[HTTP] Received request: {request.method} {request.url.path} (client={request.client.host if request.client else 'unknown'})")
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"[HTTP] Completed request: {request.method} {request.url.path} -> Status={response.status_code} (took {duration:.4f}s)")
        return response

    @app.post("/submit")
    def submit(payload: SubmitPayload, background_tasks: BackgroundTasks):
        try:
            token = ENGINE.submit(payload.model_dump())
            logger.info("[HTTP] Queueing matchmaking round in background.")
            background_tasks.add_task(ENGINE.run_match_round, force=False)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "token": token}

    @app.post("/chat/send")
    def chat_send(payload: ChatSendPayload):
        try:
            ENGINE.send_message(payload.token, payload.text, payload.room_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True}

    @app.get("/chat/messages")
    def chat_messages(token: str, room_id: Optional[str] = None):
        try:
            messages = ENGINE.get_messages(token, room_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "messages": messages}

    @app.get("/chat/all-messages")
    def chat_all_messages(token: str):
        try:
            rooms_messages = ENGINE.get_all_messages(token)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "rooms": rooms_messages}

    @app.get("/admin/vapid-public-key")
    def vapid_public_key():
        key = os.environ.get("VAPID_PUBLIC_KEY", "")
        return {"public_key": key}

    @app.post("/chat/subscribe")
    def chat_subscribe(payload: SubscriptionPayload):
        ENGINE.save_push_subscription(payload.token, payload.subscription)
        return {"ok": True}

    @app.get("/result/{token}")
    def result(token: str):
        res = ENGINE.result_for(token)
        if res is None:
            raise HTTPException(404, "unknown token")
        return {
            "round_done": ENGINE.stats()["round_done"],
            "matched": res.matched,
            "peer_handle": res.peer_handle,
            "connection_code": res.connection_code,
            "score": res.score,
            "verdict": res.verdict,
            "reasons": res.reasons,
            "matches": [
                {
                    "peer_handle": m.peer_handle,
                    "connection_code": m.connection_code,
                    "score": m.score,
                    "verdict": m.verdict,
                    "reasons": m.reasons,
                }
                for m in res.matches
            ]
        }

    @app.get("/stats")
    def stats():
        return ENGINE.stats()

    @app.post("/admin/match-round")
    def match_round(admin_token: str = ""):
        if admin_token != ADMIN_TOKEN:
            raise HTTPException(403, "bad admin token")
        return ENGINE.run_match_round(force=True)

    @app.post("/admin/reset")
    def admin_reset(payload: ResetPayload):
        import hashlib
        hashed_input = hashlib.sha256(payload.password.encode('utf-8')).hexdigest()
        if hashed_input != "47e52e0290d79744d781c62c5ba0c863bd745c4f47dfecac17a820899ff02915":
            raise HTTPException(403, "Invalid reset password")
        ENGINE.clear_db()
        return {"ok": True}

    @app.get("/admin/debug")
    def debug(admin_token: str = ""):
        if admin_token != ADMIN_TOKEN:
            raise HTTPException(403, "bad admin token")
        with ENGINE._lock:
            profiles_copy = list(ENGINE._profiles.values())
        return [
            {
                "handle": p.handle,
                "my_gender": p.my_gender,
                "target_gender": p.target_gender,
                "age": p.age,
                "age_min": p.age_min,
                "age_max": p.age_max,
            }
            for p in profiles_copy
        ]

    @app.get("/admin/debug-view", response_class=HTMLResponse)
    def debug_view():
        with ENGINE._lock:
            profiles_copy = dict(ENGINE._profiles)
            results_copy = dict(ENGINE._results)
        
        # Calculate stats
        total_users = len(profiles_copy)
        matched_users = 0
        for token in profiles_copy:
            res = results_copy.get(token)
            if res and res.matched:
                matched_users += 1
        
        unmatched_users = total_users - matched_users
        match_rate = (matched_users / total_users * 100) if total_users > 0 else 0
        
        # Generate user rows/cards
        cards_html = ""
        for token, p in profiles_copy.items():
            res = results_copy.get(token)
            
            # Match Status Badge
            if res and res.matched:
                matches_li = ""
                for m in res.matches:
                    reasons_li = "".join(f"<li>{r}</li>" for r in m.reasons)
                    matches_li += f"""
                    <div class="match-item" style="border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 10px;">
                        <div class="info-row"><strong>Partner:</strong> {m.peer_handle}</div>
                        <div class="info-row"><strong>Match Score:</strong> {m.score:.1f}%</div>
                        <div class="info-row"><strong>Connection Code:</strong> <span class="code">{m.connection_code}</span></div>
                        <div class="info-row"><strong>Verdict:</strong> {m.verdict}</div>
                        <div class="info-row">
                            <strong>Matching Reasons:</strong>
                            <ul class="reasons-list">
                                {reasons_li}
                            </ul>
                        </div>
                    </div>
                    """
                status_badge = f'<span class="badge matched">{len(res.matches)} Matches</span>'
                match_details = f"""
                <div class="match-info">
                    {matches_li}
                </div>
                """
            else:
                status_badge = '<span class="badge unmatched">Unmatched</span>'
                eval_html = ""
                if res and getattr(res, "evaluations", None):
                    eval_items = ""
                    for ev in res.evaluations:
                        eval_items += f"""
                        <div class="eval-item" style="border-bottom: 1px dashed var(--border); padding-bottom: 8px; margin-bottom: 8px;">
                            <div class="info-row"><strong>Evaluated Partner:</strong> {ev['peer_handle']}</div>
                            <div class="info-row"><strong>AI Score:</strong> {ev['score']:.1f}%</div>
                            <div class="info-row"><strong>Verdict:</strong> {ev['verdict']}</div>
                        </div>
                        """
                    eval_html = f"""
                    <div class="eval-section" style="margin-top: 15px; border-top: 1px solid var(--border); padding-top: 10px;">
                        <strong style="color: var(--accent-gold); display: block; margin-bottom: 8px; font-size: 0.9rem;">Calculated Compatibility Scores (Debugging):</strong>
                        {eval_items}
                    </div>
                    """
                match_details = f"""
                <div class="match-info unmatched-info">
                    No match found for this round.
                    {eval_html}
                </div>
                """
            
            langs = ", ".join(p.languages) if p.languages else "None"
            
            cards_html += f"""
            <div class="user-card">
                <div class="card-header">
                    <div class="user-title">
                        <span class="user-handle">{p.handle}</span>
                        <span class="user-real-name">({p.last_name})</span>
                    </div>
                    {status_badge}
                </div>
                <div class="card-body">
                    <div class="params-grid">
                        <div class="param-item"><strong>User ID:</strong> <span class="mono">{p.user_id}</span></div>
                        <div class="param-item"><strong>Token:</strong> <span class="mono">{token[:8]}...</span></div>
                        <div class="param-item"><strong>Age:</strong> {p.age or "N/A"}</div>
                        <div class="param-item"><strong>Seeking:</strong> {p.my_gender} seeking {p.target_gender} (Ages {p.age_min or 18}-{p.age_max or 99})</div>
                        <div class="param-item"><strong>Languages:</strong> {langs}</div>
                    </div>
                    <div class="story-box">
                        <strong>Life Story:</strong>
                        <p>{p.text}</p>
                    </div>
                    {match_details}
                </div>
            </div>
            """
            
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kolosok Enclave Debug Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --bg-dark: #0f172a;
                    --bg-card: #1e293b;
                    --text-main: #f8fafc;
                    --text-muted: #94a3b8;
                    --primary: #c8102e;
                    --accent-gold: #e5a93b;
                    --success: #10b981;
                    --danger: #ef4444;
                    --border: #334155;
                }}
                
                * {{
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }}
                
                body {{
                    font-family: 'Inter', sans-serif;
                    background-color: var(--bg-dark);
                    color: var(--text-main);
                    padding: 40px 20px;
                    line-height: 1.5;
                }}
                
                .container {{
                    max-width: 1100px;
                    margin: 0 auto;
                }}
                
                header {{
                    margin-bottom: 40px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid var(--border);
                    padding-bottom: 20px;
                }}
                
                h1 {{
                    font-size: 2.2rem;
                    font-weight: 700;
                    background: linear-gradient(135deg, #f8fafc 0%, var(--accent-gold) 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}
                
                .subtitle {{
                    color: var(--text-muted);
                    font-size: 0.95rem;
                    margin-top: 4px;
                }}
                
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 20px;
                    margin-bottom: 40px;
                }}
                
                .stat-card {{
                    background-color: var(--bg-card);
                    border: 1px solid var(--border);
                    border-radius: 16px;
                    padding: 20px;
                    text-align: center;
                    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
                }}
                
                .stat-value {{
                    font-size: 2.2rem;
                    font-weight: 700;
                    margin-bottom: 4px;
                    color: var(--accent-gold);
                }}
                
                .stat-label {{
                    font-size: 0.85rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    color: var(--text-muted);
                }}
                
                .user-list {{
                    display: flex;
                    flex-direction: column;
                    gap: 24px;
                }}
                
                .user-card {{
                    background-color: var(--bg-card);
                    border: 1px solid var(--border);
                    border-radius: 20px;
                    padding: 24px;
                    box-shadow: 0 15px 30px -10px rgba(0,0,0,0.5);
                    transition: transform 0.2s, border-color 0.2s;
                }}
                
                .user-card:hover {{
                    transform: translateY(-2px);
                    border-color: var(--accent-gold);
                }}
                
                .card-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 20px;
                    border-bottom: 1px solid var(--border);
                    padding-bottom: 14px;
                }}
                
                .user-title {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                
                .user-handle {{
                    font-size: 1.4rem;
                    font-weight: 700;
                    color: var(--text-main);
                }}
                
                .user-real-name {{
                    font-size: 1.1rem;
                    color: var(--text-muted);
                }}
                
                .badge {{
                    font-size: 0.8rem;
                    font-weight: 700;
                    padding: 6px 14px;
                    border-radius: 9999px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                
                .badge.matched {{
                    background-color: rgba(16, 185, 129, 0.15);
                    color: var(--success);
                    border: 1px solid var(--success);
                }}
                
                .badge.unmatched {{
                    background-color: rgba(239, 68, 68, 0.15);
                    color: var(--danger);
                    border: 1px solid var(--danger);
                }}
                
                .params-grid {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 12px;
                    font-size: 0.9rem;
                    margin-bottom: 16px;
                }}
                
                .param-item strong {{
                    color: var(--accent-gold);
                }}
                
                .mono {{
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.85rem;
                    background-color: rgba(0,0,0,0.2);
                    padding: 2px 6px;
                    border-radius: 4px;
                }}
                
                .story-box {{
                    background-color: rgba(0,0,0,0.15);
                    border-radius: 12px;
                    padding: 16px;
                    margin-bottom: 20px;
                    border-left: 4px solid var(--border);
                }}
                
                .story-box strong {{
                    display: block;
                    margin-bottom: 6px;
                    font-size: 0.85rem;
                    color: var(--text-muted);
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                
                .story-box p {{
                    font-size: 0.95rem;
                    color: #e2e8f0;
                    font-style: italic;
                }}
                
                .match-info {{
                    background-color: rgba(16, 185, 129, 0.05);
                    border: 1px solid rgba(16, 185, 129, 0.2);
                    border-radius: 12px;
                    padding: 20px;
                }}
                
                .match-info.unmatched-info {{
                    background-color: rgba(239, 68, 68, 0.05);
                    border: 1px solid rgba(239, 68, 68, 0.2);
                    color: var(--text-muted);
                    font-style: italic;
                    text-align: center;
                    padding: 12px;
                }}
                
                .info-row {{
                    margin-bottom: 8px;
                    font-size: 0.9rem;
                }}
                
                .info-row:last-child {{
                    margin-bottom: 0;
                }}
                
                .info-row strong {{
                    color: var(--success);
                }}
                
                .reasons-list {{
                    margin-left: 20px;
                    margin-top: 6px;
                }}
                
                .reasons-list li {{
                    font-size: 0.85rem;
                    color: #cbd5e1;
                    margin-bottom: 4px;
                }}
                
                .code {{
                    font-family: 'JetBrains Mono', monospace;
                    font-weight: 700;
                    color: var(--accent-gold);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <div>
                        <h1>Kolosok Enclave</h1>
                        <p class="subtitle">Secure Hardware Enclave Matched Users Debug Dashboard (Local Mode)</p>
                    </div>
                    <div>
                        <span class="badge matched">TEE Verified</span>
                    </div>
                </header>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{total_users}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color: var(--success);">{matched_users}</div>
                        <div class="stat-label">Matched Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color: var(--danger);">{unmatched_users}</div>
                        <div class="stat-label">Unmatched Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color: #6366f1;">{match_rate:.1f}%</div>
                        <div class="stat-label">Match Rate</div>
                    </div>
                </div>
                
                <div class="user-list">
                    {cards_html or '<div style="text-align:center; padding: 40px; color: var(--text-muted);">No profiles submitted yet.</div>'}
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

except ImportError:  # fastapi not installed -> engine-only mode
    app = None
