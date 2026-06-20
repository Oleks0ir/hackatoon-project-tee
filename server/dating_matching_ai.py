"""
dating_matching_ai.py

Direct Text Compatibility Matcher for a privacy-focused dating app.
Compares user-written bios and expectations directly without relying on a hardcoded set of traits.
Matches users based on dynamic keyword overlap (ignoring common stop words) and optional neural cross-encoder semantic compatibility.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Any

# Stop words list in English and German to filter out non-significant words
STOP_WORDS = {
    # English
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
    "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
    "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
    "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
    "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
    "into", "like", "love", "want", "seeking", "looking", "someone", "people", "would",
    # German
    "ich", "mich", "mir", "mein", "wir", "uns", "unser", "du", "dich", "dir", "dein", 
    "er", "ihn", "ihm", "sein", "sie", "ihr", "es", "wir", "ihr", "sie", "ist", "sind", 
    "war", "waren", "habe", "haben", "hat", "ein", "eine", "eines", "einer", "einem", 
    "einen", "der", "die", "das", "und", "aber", "oder", "weil", "als", "von", "zu", 
    "mit", "für", "über", "unter", "vor", "nach", "bei", "aus", "in", "auf", "an", "um", 
    "nicht", "nur", "sehr", "auch", "wie", "so", "dass", "da", "doch", "noch", "schon",
    "liebe", "suche", "jemand", "nach"
}

@dataclass
class UserProfile:
    id: str
    text: str
    wants: str = ""
    dealbreakers: List[str] = None

class DatingMatchingAI:
    def __init__(self, threshold: float = 75.0, verbose: bool = True):
        self.threshold = threshold
        self.verbose = verbose
        self.model_name = "cross-encoder/stsb-TinyBERT-L-4"
        self.cross_encoder = None

        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(self.model_name)
            if self.verbose:
                print(f"[DatingMatchingAI] Loaded semantic model: {self.model_name}")
        except Exception as e:
            if self.verbose:
                print("[DatingMatchingAI] WARNING: AI neural model not loaded. Using keyword compatibility fallback.")
                if str(e):
                    print(f"[DatingMatchingAI] Detail: {e}")

    def should_match(self, user_a: Dict[str, Any], user_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main compatibility evaluation endpoint. Compares raw descriptions directly.
        """
        profile_a = self._parse_user(user_a)
        profile_b = self._parse_user(user_b)

        # 1. Clean and tokenize text
        text_a_clean = self._clean(profile_a.text + " " + profile_a.wants)
        text_b_clean = self._clean(profile_b.text + " " + profile_b.wants)

        words_a = [w for w in text_a_clean.split() if w and len(w) > 2]
        words_b = [w for w in text_b_clean.split() if w and len(w) > 2]

        # 2. Filter out stop words to locate meaningful description tokens
        keywords_a = {w for w in words_a if w not in STOP_WORDS}
        keywords_b = {w for w in words_b if w not in STOP_WORDS}

        # 3. Compute Jaccard overlap similarity
        intersection = keywords_a & keywords_b
        union = keywords_a | keywords_b

        jaccard = len(intersection) / len(union) if union else 0.0

        # 4. Neural semantic similarity (if CrossEncoder is loaded)
        transformer_score = 0.0
        if self.cross_encoder is not None:
            try:
                # Direct comparison of raw stories by neural cross-encoder
                raw_score = float(self.cross_encoder.predict([(profile_a.text, profile_b.text)])[0])
                if raw_score > 1.0:
                    raw_score = raw_score / 5.0
                transformer_score = self._clamp(raw_score)
            except Exception:
                pass

        # 5. Compute compatibility score
        # Cosine/Jaccard overlap is highly indicative. We scale it up.
        # Combined with neural similarity if available.
        if transformer_score > 0.0:
            base_score = 0.5 * transformer_score + 0.5 * self._clamp(jaccard * 3.5)
        else:
            base_score = self._clamp(jaccard * 4.0)

        # 6. Apply dealbreaker penalties
        penalty_a_on_b = 0.0
        b_full_text = self._clean(profile_b.text + " " + profile_b.wants)
        if profile_a.dealbreakers:
            for db in profile_a.dealbreakers:
                db_clean = self._clean(db)
                if db_clean and db_clean in b_full_text:
                    penalty_a_on_b += 0.45

        penalty_b_on_a = 0.0
        a_full_text = self._clean(profile_a.text + " " + profile_a.wants)
        if profile_b.dealbreakers:
            for db in profile_b.dealbreakers:
                db_clean = self._clean(db)
                if db_clean and db_clean in a_full_text:
                    penalty_b_on_a += 0.45

        dealbreaker_penalty = self._clamp(max(penalty_a_on_b, penalty_b_on_a))
        final_score = self._clamp(base_score - dealbreaker_penalty)
        score = round(final_score * 100, 1)

        # 7. Generate explainable reasons dynamically using matched concepts
        reasons = []
        if intersection:
            shared_str = ", ".join(f"'{w.capitalize()}'" for w in sorted(list(intersection))[:6])
            reasons.append(f"Direct text match: Found shared concepts in stories: {shared_str}.")
        else:
            reasons.append("No directly overlapping interest keywords were found in the written descriptions.")

        if transformer_score >= 0.75:
            reasons.append("The AI model sees highly compatible contextual vibes in the stories.")
        elif transformer_score >= 0.5:
            reasons.append("The AI model sees moderate contextual alignment in the stories.")

        if dealbreaker_penalty > 0:
            reasons.append("Warning: A specified dealbreaker keyword was detected in one of the profiles.")

        details = {
            "user_a": profile_a.id,
            "user_b": profile_b.id,
            "threshold": self.threshold,
            "shared_keywords_count": len(intersection),
            "jaccard_similarity": round(jaccard, 3),
            "transformer_compatibility": round(transformer_score, 3) if transformer_score > 0 else "N/A",
            "dealbreaker_penalty": round(dealbreaker_penalty, 3)
        }

        return {
            "match": score >= self.threshold,
            "score": score,
            "verdict": self._verdict(score),
            "reasons": reasons,
            "details": details
        }

    def _parse_user(self, data: Dict[str, Any]) -> UserProfile:
        if not isinstance(data, dict):
            raise TypeError("User data must be a dictionary.")
        return UserProfile(
            id=str(data.get("id", "unknown")),
            text=str(data.get("text", "")),
            wants=str(data.get("wants", "")),
            dealbreakers=list(data.get("dealbreakers", [])) if data.get("dealbreakers") else []
        )

    def _clean(self, text: str) -> str:
        text = text.lower()
        # Keep letters (English, German/Russian characters) and digits
        text = re.sub(r"[^a-zA-Z0-9äöüßа-яа-яёё\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _verdict(self, score: float) -> str:
        if score >= 85:
            return "Excellent match"
        if score >= 75:
            return "Strong match"
        if score >= 60:
            return "Possible match"
        return "Weak match"
