"""Matching server -- the middle part of the prototype.

It sits between the web client (which collects profiles) and the AI matcher
(dating_matching_ai.DatingMatchingAI). This `prototype_no_keys` build has the
TEE crypto/attestation stripped out so the pipeline runs locally with no keys.

Flow
----
1. /submit            web client posts a raw profile {id, text, wants,
                      dealbreakers}. We KEEP the raw text (the AI matcher needs
                      it) and also compute a cheap cosine vector for prefiltering.
2. /admin/match-round prefilter candidate pairs by cheap cosine (matching.py),
                      run the expensive AI matcher only on that shortlist
                      (dating_matching_ai.py), then greedily assign each person
                      at most one partner by AI score.
3. /result/{token}    each client polls its own match.
4. /stats             content-free aggregate counts.

The core lives in `MatchEngine` (pure Python + numpy). FastAPI is an optional
thin HTTP layer on top, so the engine is importable/testable even where fastapi
is not installed (see simulate_web.py).
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import Any

from matching import candidate_pairs, embed

ADMIN_TOKEN = os.environ.get("MATCH_ADMIN_TOKEN", "let-me-match")
# AI compatibility score (0..100) at/above which a candidate pair may be matched.
AI_THRESHOLD = float(os.environ.get("MATCH_AI_THRESHOLD", "60"))
# Nearest neighbours kept per person during the cheap prefilter.
PREFILTER_TOP_K = int(os.environ.get("MATCH_PREFILTER_TOP_K", "5"))


@dataclass
class Profile:
    user_id: str
    token: str            # secret handle the client polls with
    handle: str           # what to reveal on a match (e.g. "code #7")
    # Raw text is KEPT (unlike the original enclave build) because the AI
    # matcher reads text, not vectors.
    text: str
    wants: str
    dealbreakers: list[str]
    vector: Any           # numpy array, cheap prefilter signal only


@dataclass
class MatchResult:
    matched: bool
    peer_handle: str | None = None
    connection_code: str | None = None
    score: float | None = None
    verdict: str | None = None
    reasons: list[str] = field(default_factory=list)


class MatchEngine:
    """Framework-free core. The FastAPI routes are thin wrappers over this."""

    def __init__(self, ai_threshold: float = AI_THRESHOLD) -> None:
        self._profiles: dict[str, Profile] = {}     # token -> Profile
        self._results: dict[str, MatchResult] = {}   # token -> result
        self._round_done = False
        self._ai_threshold = ai_threshold
        self._ai = None  # lazily loaded; the model is expensive to construct

    # -- submission ------------------------------------------------------
    def submit(self, profile: dict[str, Any]) -> str:
        text = str(profile.get("text", "")).strip()
        wants = str(profile.get("wants", "")).strip()
        if not text and not wants:
            raise ValueError("empty profile")
        token = secrets.token_urlsafe(16)
        user_id = secrets.token_hex(8)
        handle = str(profile.get("handle") or profile.get("id") or "someone in the room")
        dealbreakers = [str(d) for d in profile.get("dealbreakers", [])]
        # Cheap prefilter vector from the same text the AI will later read.
        vector = embed(f"{text}\n{wants}")
        self._profiles[token] = Profile(
            user_id=user_id,
            token=token,
            handle=handle,
            text=text,
            wants=wants,
            dealbreakers=dealbreakers,
            vector=vector,
        )
        self._results.setdefault(token, MatchResult(matched=False))
        return token

    # -- the one batch round --------------------------------------------
    def _matcher(self):
        if self._ai is None:
            from dating_matching_ai import DatingMatchingAI

            self._ai = DatingMatchingAI(threshold=self._ai_threshold, verbose=False)
        return self._ai

    def run_match_round(self, top_k: int = PREFILTER_TOP_K) -> dict:
        profiles = list(self._profiles.values())
        by_uid = {p.user_id: p for p in profiles}

        # 1. cheap prefilter -> shortlist of candidate pairs.
        vectors = [(p.user_id, p.vector) for p in profiles]
        shortlist = candidate_pairs(vectors, top_k=top_k)

        # 2. expensive AI matcher, only on the shortlist.
        ai = self._matcher()
        scored: list[tuple[float, str, str, str, list[str]]] = []
        for a_uid, b_uid, _cos in shortlist:
            a, b = by_uid[a_uid], by_uid[b_uid]
            res = ai.should_match(self._as_user(a), self._as_user(b))
            if res["match"]:
                scored.append(
                    (res["score"], a_uid, b_uid, res["verdict"], res["reasons"])
                )

        # 3. greedy global assignment: best AI score first, one partner each.
        scored.sort(reverse=True, key=lambda t: t[0])
        used: set[str] = set()
        pairs = 0
        for token in self._profiles:
            self._results[token] = MatchResult(matched=False)
        for score, a_uid, b_uid, verdict, reasons in scored:
            if a_uid in used or b_uid in used:
                continue
            used.update((a_uid, b_uid))
            a, b = by_uid[a_uid], by_uid[b_uid]
            code = "code #" + secrets.token_hex(2)
            self._results[a.token] = MatchResult(
                True, b.handle, code, score, verdict, reasons
            )
            self._results[b.token] = MatchResult(
                True, a.handle, code, score, verdict, reasons
            )
            pairs += 1

        self._round_done = True
        return {
            "profiles": len(profiles),
            "candidate_pairs": len(shortlist),
            "ai_calls": len(shortlist),
            "pairs": pairs,
            "unmatched": len(profiles) - 2 * pairs,
        }

    @staticmethod
    def _as_user(p: Profile) -> dict[str, Any]:
        return {
            "id": p.user_id,
            "text": p.text,
            "wants": p.wants,
            "dealbreakers": p.dealbreakers,
        }

    # -- reads -----------------------------------------------------------
    def result_for(self, token: str) -> MatchResult | None:
        if token not in self._profiles:
            return None
        return self._results.get(token, MatchResult(matched=False))

    def stats(self) -> dict:
        matched = sum(1 for r in self._results.values() if r.matched)
        return {
            "profiles": len(self._profiles),
            "matched_people": matched,
            "pairs": matched // 2,
            "round_done": self._round_done,
        }


ENGINE = MatchEngine()


# ----------------------------------------------------------------------
# Optional FastAPI HTTP layer (the actual server the web client talks to).
# Guarded so the engine above stays importable without fastapi installed.
# ----------------------------------------------------------------------
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    class SubmitPayload(BaseModel):
        id: str = ""
        handle: str = ""
        text: str = ""
        wants: str = ""
        dealbreakers: list[str] = []

    app = FastAPI(title="Matching server (prototype_no_keys)")

    @app.post("/submit")
    def submit(payload: SubmitPayload):
        try:
            token = ENGINE.submit(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "token": token}

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
        }

    @app.get("/stats")
    def stats():
        return ENGINE.stats()

    @app.post("/admin/match-round")
    def match_round(admin_token: str = ""):
        if admin_token != ADMIN_TOKEN:
            raise HTTPException(403, "bad admin token")
        return ENGINE.run_match_round()

except ImportError:  # fastapi not installed -> engine-only mode
    app = None
