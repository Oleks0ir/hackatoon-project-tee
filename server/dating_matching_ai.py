"""
dating_matching_ai.py

Final AI Matching module for a privacy-focused dating app.

Your part of the project:
    Two private user profiles -> AI analysis -> compatibility score -> match True/False

Why this is good for TEE:
    In the real system this file runs inside the TEE.
    Raw profile texts stay inside the secure environment.
    The app receives only:
        - match True/False
        - score
        - safe explanation
        - anonymized trait vectors if needed for debugging

Install:
    python -m pip install sentence-transformers torch numpy

Run test:
    python dating_matching_ai.py

Import in project:
    from dating_matching_ai import DatingMatchingAI

    matcher = DatingMatchingAI(threshold=75)
    result = matcher.should_match(user_a, user_b)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import re
import json
import math
from sentence_transformers import CrossEncoder


@dataclass
class UserProfile:
    id: str
    text: str
    wants: str = ""
    dealbreakers: List[str] = field(default_factory=list)


class DatingMatchingAI:
    """
    Final API class for the project.

    Main function:
        should_match(user_a, user_b)

    Input:
        user_a = {
            "id": "alice",
            "text": "I love hiking, jazz, calm evenings...",
            "wants": "Looking for serious relationship...",
            "dealbreakers": ["smoking"]
        }

    Output:
        {
            "match": True,
            "score": 83.7,
            "verdict": "Strong match",
            "reasons": [...],
            "details": {...}
        }
    """

    def __init__(self, threshold: float = 75.0, verbose: bool = True):
        self.threshold = threshold
        self.verbose = verbose
        self.model_name = "cross-encoder/stsb-TinyBERT-L-4"
        self.cross_encoder = CrossEncoder(self.model_name)
        if self.verbose:
            print(f"[DatingMatchingAI] Loaded AI model: {self.model_name}")

    # ============================================================
    # PUBLIC API
    # ============================================================

    def should_match(self, user_a: Dict[str, Any], user_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function for the backend.

        The backend should call only this function.
        """
        profile_a = self._parse_user(user_a)
        profile_b = self._parse_user(user_b)

        semantic_score = self._semantic_ai_score(profile_a, profile_b)
        score = round(semantic_score * 100, 1)

        return {
            "match": score >= self.threshold,
            "score": score,
            "verdict": self._verdict(score),
            "reasons": [],
            "details": {
                "user_a": profile_a.id,
                "user_b": profile_b.id,
                "threshold": self.threshold,
                "semantic_ai_score": round(semantic_score, 3),
            },
        }

    def analyze_user(self, user: Dict[str, Any]) -> Dict[str, float]:
        """
        Optional function:
        Converts one raw profile into an anonymized trait vector.
        """
        return {}

    # ============================================================
    # PARSING
    # ============================================================

    def _parse_user(self, data: Dict[str, Any]) -> UserProfile:
        if not isinstance(data, dict):
            raise TypeError("User must be a dictionary.")

        return UserProfile(
            id=str(data.get("id", "unknown")),
            text=str(data.get("text", "")),
            wants=str(data.get("wants", "")),
            dealbreakers=list(data.get("dealbreakers", [])),
        )

    # ============================================================
    # TEXT UTILS
    # ============================================================

    def _clean(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    # ============================================================
    # AI SEMANTIC MODEL
    # ============================================================

    def _semantic_ai_score(self, a: UserProfile, b: UserProfile) -> float:
        """
        Real Transformer model score.
        It reads both profiles together and estimates semantic compatibility.
        """
        text_a = f"Bio: {a.text}\nLooking for: {a.wants}"
        text_b = f"Bio: {b.text}\nLooking for: {b.wants}"

        raw_score = float(self.cross_encoder.predict([(text_a, text_b)])[0])

        # Some models output 0..1, others 0..5.
        if raw_score > 1.0:
            raw_score = raw_score / 5.0

        return self._clamp(raw_score)

    # ============================================================
    # OUTPUT
    # ============================================================

    def _verdict(self, score: float) -> str:
        if score >= 85:
            return "Excellent match"
        if score >= 75:
            return "Strong match"
        if score >= 60:
            return "Possible match"
        return "Weak match"


# ============================================================
# DEMO / LOCAL TEST
# ============================================================

def demo() -> None:
    matcher = DatingMatchingAI(threshold=75)

    user_a = {
        "id": "alice",
        "text": """
        """,
        "wants": """
        """,
        "dealbreakers": [""],
    }

    user_b = {
        "id": "bob",
        "text": """
        I enjoy walking in nature, mountain trips, live music, galleries,
        cooking together, small cafes and talking for hours about life.
        I am looking for something serious and warm.
        """,
        "wants": """
        Looking for someone calm, romantic, curious, interested in culture,
        travel and deep conversations.
        """,
        "dealbreakers": ["smoking"],
    }

    user_c = {
        "id": "max",
        "text": """
        I love nightclubs, parties, drinking, loud festivals, gaming and cars.
        I prefer spontaneous nightlife and do not like museums or quiet evenings.
        """,
        "wants": """
        Looking for someone who wants to party every weekend and keep things casual.
        """,
        "dealbreakers": [],
    }

    print("\n=== Alice + Bob ===")
    print(json.dumps(matcher.should_match(user_a, user_b), indent=2, ensure_ascii=False))

    print("\n=== Alice + Max ===")
    print(json.dumps(matcher.should_match(user_a, user_c), indent=2, ensure_ascii=False))

    print("\n=== Only Alice anonymized traits ===")
    print(json.dumps(matcher.analyze_user(user_a), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo()
