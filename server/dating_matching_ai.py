"""
dating_matching_ai.py

Final AI Matching module for a privacy-focused dating app.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import re
import json
import math


@dataclass
class UserProfile:
    id: str
    text: str
    wants: str = ""
    dealbreakers: List[str] = field(default_factory=list)


class DatingMatchingAI:
    """
    Final API class for the project.
    """

    def __init__(self, threshold: float = 75.0, verbose: bool = True):
        self.threshold = threshold
        self.verbose = verbose
        self.model_name = "cross-encoder/stsb-TinyBERT-L-4"
        self.cross_encoder = None

        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(self.model_name)
            if self.verbose:
                print(f"[DatingMatchingAI] Loaded AI model: {self.model_name}")
        except Exception as e:
            if self.verbose:
                print("[DatingMatchingAI] WARNING: AI model not loaded.")
                print("[DatingMatchingAI] Reason:", str(e))
                print("[DatingMatchingAI] Fallback mode enabled.")

    def should_match(self, user_a: Dict[str, Any], user_b: Dict[str, Any]) -> Dict[str, Any]:
        profile_a = self._parse_user(user_a)
        profile_b = self._parse_user(user_b)

        traits_a = self._extract_traits(profile_a)
        traits_b = self._extract_traits(profile_b)

        semantic_score = self._semantic_ai_score(profile_a, profile_b)
        values_score = self._values_compatibility(traits_a, traits_b)
        lifestyle_score = self._lifestyle_compatibility(traits_a, traits_b)
        social_score = self._social_energy_compatibility(traits_a, traits_b)
        intent_score = self._relationship_intent_compatibility(traits_a, traits_b)

        dealbreaker_penalty = max(
            self._dealbreaker_penalty(profile_a, profile_b),
            self._dealbreaker_penalty(profile_b, profile_a),
        )

        final_score_0_1 = (
            0.75 * semantic_score +
            0.077 * values_score +
            0.077 * lifestyle_score +
            0.058 * social_score +
            0.038 * intent_score -
            0.45 * dealbreaker_penalty
        )

        final_score_0_1 = self._clamp(final_score_0_1)
        score = round(final_score_0_1 * 100, 1)

        return {
            "match": score >= self.threshold,
            "score": score,
            "verdict": self._verdict(score),
            "reasons": self._safe_explanation(
                semantic_score=semantic_score,
                values_score=values_score,
                lifestyle_score=lifestyle_score,
                social_score=social_score,
                intent_score=intent_score,
                penalty=dealbreaker_penalty,
                traits_a=traits_a,
                traits_b=traits_b,
            ),
            "details": {
                "user_a": profile_a.id,
                "user_b": profile_b.id,
                "threshold": self.threshold,
                "semantic_ai_score": round(semantic_score, 3),
                "values_score": round(values_score, 3),
                "lifestyle_score": round(lifestyle_score, 3),
                "social_energy_score": round(social_score, 3),
                "relationship_intent_score": round(intent_score, 3),
                "dealbreaker_penalty": round(dealbreaker_penalty, 3),
            },
        }

    def analyze_user(self, user: Dict[str, Any]) -> Dict[str, float]:
        profile = self._parse_user(user)
        return self._extract_traits(profile)

    def _parse_user(self, data: Dict[str, Any]) -> UserProfile:
        if not isinstance(data, dict):
            raise TypeError("User must be a dictionary.")

        return UserProfile(
            id=str(data.get("id", "unknown")),
            text=str(data.get("text", "")),
            wants=str(data.get("wants", "")),
            dealbreakers=list(data.get("dealbreakers", [])),
        )

    def _clean(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _contains_count(self, text: str, keywords: List[str]) -> int:
        clean_text = self._clean(text)
        count = 0

        for keyword in keywords:
            keyword_clean = self._clean(keyword)
            if keyword_clean and keyword_clean in clean_text:
                count += 1

        return count

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _closeness(self, a: float, b: float) -> float:
        return 1.0 - abs(a - b)

    def _extract_traits(self, profile: UserProfile) -> Dict[str, float]:
        text = f"{profile.text}\nLooking for: {profile.wants}"

        trait_keywords = {
            "introversion": [
                "quiet", "calm", "home", "cozy", "reading", "small circle",
                "deep conversations", "introvert",
                "спокойный", "тихий", "дом", "уют", "читать", "интроверт",
                "глубокие разговоры",
            ],
            "extraversion": [
                "social", "friends", "people", "events", "outgoing", "talkative",
                "экстраверт", "общение", "люди", "друзья", "мероприятия",
            ],
            "travel": [
                "travel", "trip", "explore", "countries", "europe", "asia",
                "adventure", "city trips",
                "путешествия", "поездки", "страны", "европа", "азия",
                "приключения",
            ],
            "culture": [
                "museum", "art", "books", "cinema", "theatre", "jazz", "music",
                "gallery", "concert", "poetry",
                "музей", "искусство", "книги", "кино", "театр", "джаз",
                "музыка", "галерея", "концерт",
            ],
            "sport": [
                "sport", "fitness", "gym", "running", "hiking", "mountain",
                "cycling", "climbing", "yoga", "swimming",
                "спорт", "зал", "бег", "поход", "горы", "йога", "фитнес",
            ],
            "career_focus": [
                "career", "startup", "business", "ambitious", "university",
                "study", "work", "goals", "building something",
                "карьера", "стартап", "бизнес", "амбиции", "университет",
                "учеба", "работа", "цели",
            ],
            "family_orientation": [
                "family", "serious relationship", "marriage", "kids", "children",
                "long term", "settle down",
                "семья", "серьезные отношения", "брак", "дети",
                "долгосрочные отношения",
            ],
            "party_lifestyle": [
                "party", "club", "nightlife", "drinking", "festival", "rave",
                "тусовки", "клубы", "вечеринки", "алкоголь", "рейв",
            ],
            "calm_lifestyle": [
                "calm", "quiet", "cozy", "walk", "coffee", "home", "slow life",
                "small cafes",
                "спокойный", "тихий", "уют", "прогулки", "кофе", "дом",
            ],
            "romantic": [
                "romantic", "romance", "affection", "warm", "love", "caring",
                "tender", "emotionally mature",
                "романтика", "романтичный", "любовь", "забота", "теплый",
            ],
            "intellectual": [
                "philosophy", "psychology", "science", "history", "deep talks",
                "learning", "debates", "curious",
                "философия", "психология", "наука", "история",
                "глубокие разговоры", "учиться",
            ],
            "spontaneity": [
                "spontaneous", "random trips", "adventure", "last minute",
                "surprise",
                "спонтанный", "приключения", "внезапные поездки",
            ],
            "serious_intent": [
                "serious relationship", "long term", "family", "marriage",
                "something serious", "commitment",
                "серьезные отношения", "долгосрочные отношения", "семья",
                "брак",
            ],
            "casual_intent": [
                "casual", "no commitment", "just fun", "nothing serious",
                "keep things casual",
                "без обязательств", "ничего серьезного", "просто весело",
            ],
        }

        traits = {}

        for trait, keywords in trait_keywords.items():
            hits = self._contains_count(text, keywords)

            if hits == 0:
                value = 0.15
            elif hits == 1:
                value = 0.45
            elif hits == 2:
                value = 0.70
            else:
                value = 0.95

            traits[trait] = value

        self._smooth_opposites(traits)

        return traits

    def _smooth_opposites(self, traits: Dict[str, float]) -> None:
        opposites = [
            ("introversion", "extraversion"),
            ("calm_lifestyle", "party_lifestyle"),
            ("serious_intent", "casual_intent"),
        ]

        for a, b in opposites:
            if traits[a] > 0.65:
                traits[b] = min(traits[b], 0.35)
            if traits[b] > 0.65:
                traits[a] = min(traits[a], 0.35)

    def _semantic_ai_score(self, a: UserProfile, b: UserProfile) -> float:
        text_a = f"Bio: {a.text}\nLooking for: {a.wants}"
        text_b = f"Bio: {b.text}\nLooking for: {b.wants}"

        if self.cross_encoder is not None:
            raw_score = float(self.cross_encoder.predict([(text_a, text_b)])[0])
            if raw_score > 1.0:
                raw_score = raw_score / 5.0
            return self._clamp(raw_score)

        # Safe fallback if model is unavailable.
        words_a = set(self._clean(text_a).split())
        words_b = set(self._clean(text_b).split())

        if not words_a or not words_b:
            return 0.0

        return self._clamp(3.0 * len(words_a & words_b) / len(words_a | words_b))

    def _values_compatibility(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        keys = [
            "family_orientation",
            "career_focus",
            "romantic",
            "intellectual",
            "spontaneity",
        ]
        return sum(self._closeness(a[k], b[k]) for k in keys) / len(keys)

    def _lifestyle_compatibility(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        keys = [
            "travel",
            "culture",
            "sport",
            "calm_lifestyle",
            "party_lifestyle",
        ]
        return sum(self._closeness(a[k], b[k]) for k in keys) / len(keys)

    def _social_energy_compatibility(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        keys = [
            "introversion",
            "extraversion",
            "calm_lifestyle",
            "party_lifestyle",
        ]
        return sum(self._closeness(a[k], b[k]) for k in keys) / len(keys)

    def _relationship_intent_compatibility(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        serious_match = self._closeness(a["serious_intent"], b["serious_intent"])
        casual_match = self._closeness(a["casual_intent"], b["casual_intent"])

        conflict = 0.0
        if a["serious_intent"] > 0.65 and b["casual_intent"] > 0.65:
            conflict = 0.5
        if b["serious_intent"] > 0.65 and a["casual_intent"] > 0.65:
            conflict = 0.5

        return self._clamp((serious_match + casual_match) / 2 - conflict)

    def _dealbreaker_penalty(self, a: UserProfile, b: UserProfile) -> float:
        b_text = self._clean(b.text + " " + b.wants)
        penalty = 0.0

        for dealbreaker in a.dealbreakers:
            dealbreaker_clean = self._clean(dealbreaker)
            if dealbreaker_clean and dealbreaker_clean in b_text:
                penalty += 0.35

        return self._clamp(penalty)

    def _verdict(self, score: float) -> str:
        if score >= 85:
            return "Excellent match"
        if score >= 75:
            return "Strong match"
        if score >= 60:
            return "Possible match"
        return "Weak match"

    def _safe_explanation(
        self,
        semantic_score: float,
        values_score: float,
        lifestyle_score: float,
        social_score: float,
        intent_score: float,
        penalty: float,
        traits_a: Dict[str, float],
        traits_b: Dict[str, float],
    ) -> List[str]:
        reasons = []

        if semantic_score >= 0.65:
            reasons.append("The AI model sees strong semantic compatibility between the profiles.")
        elif semantic_score >= 0.45:
            reasons.append("The AI model sees moderate semantic compatibility between the profiles.")
        else:
            reasons.append("The AI model sees limited semantic compatibility between the profiles.")

        if values_score >= 0.75:
            reasons.append("Their deeper values and relationship expectations look aligned.")
        elif values_score < 0.55:
            reasons.append("Their deeper values may differ.")

        if lifestyle_score >= 0.75:
            reasons.append("Their lifestyle patterns look similar.")
        elif lifestyle_score < 0.55:
            reasons.append("Their lifestyle patterns may be different.")

        if social_score >= 0.75:
            reasons.append("Their social energy looks compatible.")
        elif social_score < 0.55:
            reasons.append("Their social energy may clash.")

        if intent_score >= 0.75:
            reasons.append("Their relationship intentions seem aligned.")
        elif intent_score < 0.55:
            reasons.append("Their relationship intentions may not align.")

        shared = []
        for trait in traits_a:
            if trait in ["serious_intent", "casual_intent"]:
                continue
            if traits_a[trait] >= 0.65 and traits_b.get(trait, 0.0) >= 0.65:
                shared.append(trait)

        if shared:
            reasons.append("Shared strong compatibility signals: " + ", ".join(shared[:5]) + ".")

        if penalty > 0:
            reasons.append("A dealbreaker was detected, so the score was reduced.")

        return reasons


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
