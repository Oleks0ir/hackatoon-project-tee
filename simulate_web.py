"""Stand-in for the web frontend.

The real web client (a separate, not-yet-written program) will POST profiles to
app.py's HTTP endpoints. This script plays that role so we can exercise the whole
pipeline end to end -- submit profiles -> run the match round -> poll results --
without a browser or a running server.

It drives `MatchEngine` directly, which is exactly what the FastAPI routes in
app.py do. Run:

    python simulate_web.py
"""
from __future__ import annotations

from app import ENGINE

# A small room of people. Some should pair up, some should be left unmatched --
# "no good match" is an allowed outcome.
PROFILES = [
    {
        "id": "alice",
        "text": "I love hiking, mountain trips, jazz, galleries and long calm "
                "evenings cooking and talking for hours about life and ideas.",
        "wants": "Someone calm, romantic and curious, into culture, travel and "
                 "deep conversations. Looking for something serious.",
        "dealbreakers": ["smoking"],
    },
    {
        "id": "bob",
        "text": "Walking in nature, live music, small cafes, museums and reading. "
                "I like quiet weekends and deep talks.",
        "wants": "Looking for something serious and warm, someone into culture "
                 "and travel.",
        "dealbreakers": [],
    },
    {
        "id": "max",
        "text": "Nightclubs, parties, drinking, loud festivals, gaming and cars. "
                "Spontaneous nightlife, not into museums or quiet evenings.",
        "wants": "Someone who wants to party every weekend and keep things casual.",
        "dealbreakers": [],
    },
    {
        "id": "nina",
        "text": "Clubbing, festivals, parties and travel for the nightlife. "
                "I love meeting lots of new people and going out constantly.",
        "wants": "Casual fun, no commitment, lots of partying.",
        "dealbreakers": [],
    },
    {
        "id": "sam",
        "text": "Startup founder, very career focused, ambitious, always building "
                "something. Gym in the mornings, work the rest of the day.",
        "wants": "Someone ambitious and independent with their own goals.",
        "dealbreakers": [],
    },
]


def main() -> None:
    # 1. web client submits each profile -> server hands back a poll token.
    tokens: dict[str, str] = {}
    for profile in PROFILES:
        token = ENGINE.submit(profile)
        tokens[profile["id"]] = token
        print(f"submitted {profile['id']:<6} -> token {token[:10]}...")

    # 2. presenter triggers the one synchronized round.
    print("\nrunning match round...")
    summary = ENGINE.run_match_round()
    print("round summary:", summary)

    # 3. each client polls its own result.
    print("\nresults:")
    for uid, token in tokens.items():
        res = ENGINE.result_for(token)
        if res and res.matched:
            print(f"  {uid:<6} -> matched with {res.peer_handle} "
                  f"(score {res.score}, {res.verdict}) {res.connection_code}")
            for reason in res.reasons:
                print(f"           - {reason}")
        else:
            print(f"  {uid:<6} -> no match this round")


if __name__ == "__main__":
    main()
