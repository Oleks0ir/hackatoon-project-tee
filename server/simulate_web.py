"""Stand-in for the web frontend.

The real web client (a separate service) POSTs profiles to app.py's HTTP
endpoints. This script plays that role so we can exercise the whole pipeline end
to end -- submit profiles -> run the match round -> poll results -- without a
browser or a running server. It drives `MatchEngine` directly, which is exactly
what the FastAPI routes in app.py do.

Profiles use the real users-API shape (profile / demographics / matching_data).

Run:
    python simulate_web.py
"""
from __future__ import annotations

from app import ENGINE


def profile(first, emoji, my_gender, target, age, lo, hi, langs, story):
    return {
        "profile": {"first_name": first, "last_name": "Doe",
                    "avatar_index": 1, "avatar_emoji": emoji},
        "demographics": {"my_gender": my_gender, "target_gender": target,
                         "age": age, "age_range": {"min": lo, "max": hi},
                         "languages": langs},
        "matching_data": {"story": story},
    }


# A small room. Note the demographic gates: Serafim<->Lena should pair (mutual
# gender + age fit + compatible stories); Max<->Nina pair on party lifestyle;
# Tom only wants men so he can't match the women regardless of his story.
PROFILES = [
    profile("Serafim", "🦊", "Male", "Female", 24, 21, 35, ["English", "German"],
            "I study computer science at TUM. Into cybersecurity, cryptography "
            "and hiking in the Alps. Looking for someone who loves technology, "
            "outdoor adventures and deep talks over coffee."),
    profile("Lena", "🦋", "Female", "Male", 26, 22, 32, ["English", "German"],
            "Software engineer who loves mountain hikes, climbing and quiet "
            "evenings reading about cryptography. Looking for someone curious "
            "and into the outdoors and long conversations."),
    profile("Max", "🐺",  "Male", "Female", 28, 21, 35, ["English"],
            "Nightclubs, festivals, parties and gaming. Spontaneous nightlife, "
            "not into museums. Looking for casual fun, no commitment."),
    profile("Nina", "🦅", "Female", "Male", 25, 23, 33, ["English"],
            "Clubbing, festivals and going out constantly. Love meeting new "
            "people. Looking for casual fun and lots of partying."),
    profile("Tom", "🐯",  "Male", "Male", 30, 25, 40, ["English"],
            "Hiking, cryptography and coffee. Looking for a thoughtful guy who "
            "loves the outdoors and deep discussions."),
]


def main() -> None:
    # 1. web client submits each profile -> server hands back a poll token.
    tokens: dict[str, str] = {}
    for p in PROFILES:
        token = ENGINE.submit(p)
        name = p["profile"]["first_name"]
        tokens[name] = token
        print(f"submitted {name:<8} -> token {token[:10]}...")

    # 2. presenter triggers the one synchronized round.
    print("\nrunning match round...")
    summary = ENGINE.run_match_round()
    print("round summary:", summary)

    # 3. each client polls its own result.
    print("\nresults:")
    for name, token in tokens.items():
        res = ENGINE.result_for(token)
        if res and res.matched:
            print(f"  {name:<8} -> matched with {res.peer_handle} "
                  f"(score {res.score}, {res.verdict}) {res.connection_code}")
            for reason in res.reasons:
                print(f"             - {reason}")
        else:
            print(f"  {name:<8} -> no match this round")


if __name__ == "__main__":
    main()
