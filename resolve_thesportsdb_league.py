"""
resolve_thesportsdb_league.py — resolve a VERIFIED TheSportsDB league ID.

Champions League and Europa League are deliberately unmapped (UNRESOLVED_LEAGUES
in data/thesportsdb_fixtures.py). HR35: a wrong league ID silently returns
another competition's fixtures, which is worse than an honest gap. The shared
public test key truncates the league directory to 5 entries, so resolving
continental competitions needs a PERSONAL key.

This tool is READ-ONLY. It never writes a mapping — it finds candidate IDs,
checks the current-season event feed (so you can confirm the qualifying rounds
you care about are actually filed there), and prints what to add. A human adds
the verified ID to LEAGUE_IDS in data/thesportsdb_fixtures.py.

Usage:
    py -3.12 resolve_thesportsdb_league.py --competition "Champions League"
    py -3.12 resolve_thesportsdb_league.py --competition "Champions League" "Europa League"
    py -3.12 resolve_thesportsdb_league.py --season 2627 --competition "Champions League"

Prereq: THESPORTSDB_KEY set in .env (free at thesportsdb.com/register.php).
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config  # loads .env, so THESPORTSDB_KEY is picked up
from data.thesportsdb_fixtures import API_BASE, PUBLIC_TEST_KEY, _get_key, _season_label


def _api(key: str, endpoint: str, params: dict) -> dict:
    import requests
    url = f"{API_BASE}/{key}/{endpoint}.php"
    return requests.get(url, params=params, timeout=30).json()


def resolve(key: str, season: str, competition: str) -> list[dict]:
    """Return candidate leagues for one competition, each with an event check.

    The `events` sub-dict has {'count', 'sample': [fixture strings]}; the caller
    prints the decision. Never writes anything."""
    # Phrase match, not substring-per-word: "Champions League" must appear as a
    # phrase, so "English League Championship" (which contains the word
    # "champions") can never be resolved as the Champions League. "UEFA
    # Champions League" and "CAF Champions League" both contain the phrase, so
    # the tool lists every real candidate and a human picks the UEFA one.
    needle = competition.lower()
    directory = _api(key, "all_leagues", {})["leagues"]
    matches = []
    for L in directory:
        hay = " ".join(str(L.get(k) or "") for k in
                       ("strLeague", "strLeagueAlternate", "strSport")).lower()
        if needle in hay:
            lid = L["idLeague"]
            events = _api(key, "eventsseason",
                          {"id": lid, "s": season}).get("events") or []
            matches.append({
                "id": lid,
                "name": L.get("strLeague"),
                "country": L.get("strCountry", ""),
                "sport": L.get("strSport"),
                "event_count": len(events),
                "sample": [f"{e.get('dateEvent','?')}  {e.get('strHomeTeam')} v "
                           f"{e.get('strAwayTeam')}  [{e.get('strRound','')}]"
                           for e in events[:3]],
            })
    return matches


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--competition", nargs="+", required=True,
                    help="competition name(s), e.g. 'Champions League'")
    ap.add_argument("--season", default="2627",
                    help="season code, e.g. 2627 -> TheSportsDB 2026-2027")
    a = ap.parse_args()

    key = _get_key()
    season = _season_label(a.season)
    if key == PUBLIC_TEST_KEY:
        print("WARNING: running on the shared test key — the directory is "
              "truncated, so continental resolution will almost certainly fail. "
              "Set THESPORTSDB_KEY in .env to a personal key.\n")
    else:
        print(f"Using personal key (…{key[-4:]}) — full directory available.\n")

    for name in a.competition:
        print(f"===== {name} =====")
        for m in resolve(key, season, name):
            print(f"  candidate id={m['id']} | {m['name']} ({m['country']}) "
                  f"| sport={m['sport']}")
            if m["event_count"]:
                print(f"    -> {m['event_count']} events for {season}; first:")
                for s in m["sample"]:
                    print(f"       {s}")
                print(f"    SUGGESTED: add '{name}': {m['id']} to LEAGUE_IDS in "
                      f"data/thesportsdb_fixtures.py once you confirm the round "
                      f"names include the qualifying rounds you care about.")
            else:
                print(f"    -> NO events for {season} under this id (different "
                      f"season code, or qualifiers are filed elsewhere).")
        print()


if __name__ == "__main__":
    main()
