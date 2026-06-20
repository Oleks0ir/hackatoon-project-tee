"""Load test: ~300 simulated people through the two-stage pipeline.

Generates a roomful of varied profiles, submits them, and runs one match round.
The point is to show what the cheap prefilter buys us: instead of running the
expensive AI matcher on all N*(N-1)/2 pairs, it only runs on the shortlist.

Run:
    python simulate_load.py            # default 300 people
    python simulate_load.py 500 8      # 500 people, top_k=8
"""
from __future__ import annotations

import random
import sys
import time

from app import MatchEngine

# Archetypes: each has pools of phrases so generated profiles vary in wording
# (otherwise every same-type person would be an identical vector).
ARCHETYPES = {
    "calm_culture": {
        "text": ["hiking", "mountain trips", "jazz", "art galleries", "museums",
                 "reading novels", "live music", "small cafes", "cooking at home",
                 "long walks", "poetry", "deep conversations", "quiet evenings"],
        "wants": ["someone calm and curious", "into culture and travel",
                  "looking for something serious", "warm and romantic",
                  "deep talks and slow weekends"],
        "deal": [["smoking"], [], ["partying every night"]],
    },
    "party_casual": {
        "text": ["nightclubs", "festivals", "parties", "loud music", "gaming",
                 "cars", "nightlife", "drinking with friends", "raves",
                 "spontaneous trips", "meeting new people", "going out constantly"],
        "wants": ["casual fun no commitment", "party every weekend",
                  "keep things light", "someone spontaneous", "nothing serious"],
        "deal": [[], ["museums"], ["staying home"]],
    },
    "career_ambitious": {
        "text": ["startup founder", "very career focused", "always building something",
                 "ambitious goals", "gym in the mornings", "business books",
                 "networking", "investing", "long work days", "self improvement"],
        "wants": ["someone ambitious and independent", "with their own goals",
                  "driven and focused", "supportive of a busy life"],
        "deal": [[], ["no ambition"]],
    },
    "family_serious": {
        "text": ["family is everything", "want kids someday", "cozy home life",
                 "cooking together", "long term relationship", "settling down",
                 "weekend markets", "gardening", "board game nights", "caring and warm"],
        "wants": ["serious relationship leading to family", "marriage and kids",
                  "someone who wants to settle down", "long term and committed"],
        "deal": [["just casual"], ["no commitment"], []],
    },
    "sporty_outdoors": {
        "text": ["running", "cycling", "climbing", "yoga", "swimming", "trail runs",
                 "marathons", "camping", "surfing", "fitness", "early mornings outside"],
        "wants": ["an active partner", "someone who loves the outdoors",
                  "shared adventures", "healthy and energetic"],
        "deal": [[], ["smoking"]],
    },
}


def make_profile(i: int, rng: random.Random) -> dict:
    kind = rng.choice(list(ARCHETYPES.keys()))
    a = ARCHETYPES[kind]
    text = ", ".join(rng.sample(a["text"], k=rng.randint(4, 7)))
    wants = " ".join(rng.sample(a["wants"], k=rng.randint(1, 2)))
    deal = rng.choice(a["deal"])
    return {
        "id": f"user{i:03d}_{kind}",
        "text": f"I'm into {text}.",
        "wants": wants,
        "dealbreakers": list(deal),
    }


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    rng = random.Random(42)

    engine = MatchEngine()
    tokens = {}
    for i in range(n):
        p = make_profile(i, rng)
        tokens[p["id"]] = engine.submit(p)

    full_pairs = n * (n - 1) // 2
    print(f"people: {n}   top_k: {top_k}")
    print(f"all possible pairs (naive AI calls): {full_pairs:,}")

    t0 = time.perf_counter()
    summary = engine.run_match_round(top_k=top_k)
    elapsed = time.perf_counter() - t0

    cand = summary["candidate_pairs"]
    saved = 100 * (1 - cand / full_pairs) if full_pairs else 0.0
    print(f"\nprefilter shortlist (actual AI calls): {cand:,}")
    print(f"reduction vs naive: {saved:.1f}%  ({full_pairs:,} -> {cand:,})")
    print(f"matched pairs: {summary['pairs']}   unmatched people: {summary['unmatched']}")
    print(f"round time: {elapsed:.2f}s  ({1000 * elapsed / max(cand, 1):.2f} ms / AI call)")

    # spot-check: show a few matches by archetype to sanity-check quality.
    print("\nsample matches:")
    shown = 0
    seen = set()
    for uid, token in tokens.items():
        if uid in seen:
            continue
        res = engine.result_for(token)
        if res and res.matched:
            print(f"  {uid:<22} <-> {res.peer_handle:<22} "
                  f"score {res.score}  ({res.verdict})")
            seen.add(uid)
            seen.add(res.peer_handle)
            shown += 1
            if shown >= 8:
                break


if __name__ == "__main__":
    main()
