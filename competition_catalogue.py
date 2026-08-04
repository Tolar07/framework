"""
EUROPEAN COMPETITION CATALOGUE — what exists, and which of our sources carry it.

Built by QUERYING the sources, not by reciting a list. A hand-written register
of "leagues we could add" is exactly the kind of artefact that goes stale and
then gets trusted: the framework's own source table listed Croatia as
Football-Data extra-league code CRO, and that code does not exist (it 404s;
CRA is Brazil). This module regenerates the answer from live directories every
time it runs, so the register cannot drift away from reality.

For each competition it reports the three things that decide whether it can
ever produce a board row:

  HISTORY   — can the engine be fitted?     (football-data.co.uk / API-Football)
  FIXTURES  — is there anything to predict?  (TheSportsDB / The Odds API)
  ODDS      — is there an entry price?       (The Odds API)

A competition needs all three. Two out of three is still NO DATA — PENDING.

    python competition_catalogue.py --top-flights   # first tier only
    python competition_catalogue.py --cups          # domestic cups
    python competition_catalogue.py --country Croatia
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import requests
except ImportError:
    requests = None

from data.football_data_source import LEAGUE_CODES, EXTRA_CODES
from data import thesportsdb_fixtures as tsdb
from data.api_football_results import LEAGUE_IDS as APIF_IDS
import pipeline.odds as odds_mod

CACHE = Path(__file__).parent / "data" / "cache" / "api_football_leagues.json"

# UEFA members plus 'World', where the continental competitions are filed.
EUROPE = {
    "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
    "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus",
    "Czech-Republic", "Denmark", "England", "Estonia", "Faroe Islands",
    "Finland", "France", "Georgia", "Germany", "Gibraltar", "Greece",
    "Hungary", "Iceland", "Ireland", "Israel", "Italy", "Kazakhstan",
    "Kosovo", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta",
    "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia",
    "Northern Ireland", "Norway", "Poland", "Portugal", "Romania", "Russia",
    "San Marino", "Scotland", "Serbia", "Slovakia", "Slovenia", "Spain",
    "Sweden", "Switzerland", "Turkey", "Ukraine", "Wales", "World",
}


def load_catalogue(refresh: bool = False) -> list[dict]:
    """API-Football's own directory — the broadest of the three, so it defines
    the universe of competitions the others are checked against."""
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text(encoding="utf-8"))["response"]
    if requests is None:
        raise RuntimeError("requests not installed")
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY not set and no cached catalogue")
    r = requests.get("https://v3.football.api-sports.io/leagues",
                      headers={"x-apisports-key": key}, timeout=60)
    r.raise_for_status()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(r.json()), encoding="utf-8")
    return r.json()["response"]


def _odds_keys() -> set[str]:
    """Sport keys the odds provider currently lists as active. A competition
    out of season simply isn't listed, which is why a 'no' here can turn into
    a 'yes' once the competition kicks off."""
    if requests is None:
        return set()
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return set()
    try:
        r = requests.get("https://api.the-odds-api.com/v4/sports",
                          params={"apiKey": key}, timeout=25)
        return {s["title"].lower() for s in r.json()}
    except Exception:
        return set()


# The framework's internal names differ from API-Football's. Mapping them
# explicitly stops the coverage table reporting "no history" for competitions
# we demonstrably hold — a misleading coverage table is worse than none.
FRAMEWORK_NAME = {
    "UEFA Champions League": "Champions League",
    "UEFA Europa League": "Europa League",
    "UEFA Europa Conference League": "Conference League",
    "Premier League": "Premier League",
    "La Liga": "La Liga",
    "Serie A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Ligue 1": "Ligue 1",
    "Eredivisie": "Eredivisie",
    "Primeira Liga": "Primeira Liga",
    "Jupiler Pro League": "Belgian Pro League",
    "Premiership": "Scottish Premiership",
    "Superliga": "Danish Superliga",
    "Ekstraklasa": "Ekstraklasa",
    "Championship": "Championship",
    "HNL": "HNL",
}


def coverage(name: str, country: str, odds_titles: set[str]) -> dict:
    """Which of our sources actually carry this competition.

    HISTORY counts BOTH football-data.co.uk (which also carries the odds the
    CLV backtest needs) and API-Football (broad, but its free tier stops at
    2024, so anything sourced there is stale — flagged, not hidden).
    """
    # Competition names are NOT unique across Europe, and a collision credits
    # one country's competition with another's coverage. Scotland's
    # Championship was being shown as fully covered because it inherited the
    # ENGLISH Championship's sources. Each mapped name is therefore pinned to
    # the one country it belongs to.
    HOME_COUNTRY = {
        "Superliga": "Denmark", "Premiership": "Scotland",
        "Championship": "England", "Premier League": "England",
        "Serie A": "Italy", "Bundesliga": "Germany", "La Liga": "Spain",
        "Ligue 1": "France", "Eredivisie": "Netherlands",
        "Primeira Liga": "Portugal", "Ekstraklasa": "Poland",
        "Jupiler Pro League": "Belgium", "HNL": "Croatia",
    }
    if name in HOME_COUNTRY and country != HOME_COUNTRY[name]:
        # Namespace it so it CANNOT match. Falling back to the bare name was
        # not enough: "Championship" is itself the framework's key for the
        # English competition, so Scotland's Championship kept inheriting it.
        fw = f"{country}::{name}"
    else:
        fw = FRAMEWORK_NAME.get(name, name)

    fd = bool(LEAGUE_CODES.get(fw)) or fw in EXTRA_CODES
    apif_has = fw in APIF_IDS
    return {
        "history_fd": fd,
        "history_apif": apif_has,
        "history": fd or apif_has,
        "thesportsdb": fw in tsdb.LEAGUE_IDS,
        "odds_api": fw in odds_mod.SPORT_KEYS or name.lower() in odds_titles,
        "framework_name": fw,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-flights", action="store_true",
                     help="first-tier domestic leagues only")
    ap.add_argument("--cups", action="store_true", help="domestic cups only")
    ap.add_argument("--country")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    rows = [x for x in load_catalogue(a.refresh)
            if x["country"]["name"] in EUROPE]
    if a.country:
        rows = [x for x in rows if x["country"]["name"].lower() == a.country.lower()]
    if a.cups:
        rows = [x for x in rows if x["league"]["type"] == "Cup"]
    elif a.top_flights:
        rows = [x for x in rows if x["league"]["type"] == "League"]

    odds_titles = _odds_keys()
    by_country: dict[str, list] = {}
    for x in rows:
        by_country.setdefault(x["country"]["name"], []).append(x)

    print(f"EUROPEAN COMPETITION CATALOGUE — {len(rows)} competitions, "
          f"{len(by_country)} countries")
    print("Sources: FD=football-data.co.uk  TSD=TheSportsDB  ODDS=The Odds API")
    print("=" * 96)

    ready = 0
    for country in sorted(by_country):
        comps = sorted(by_country[country], key=lambda x: x["league"]["name"])
        print(f"\n{country}  ({len(comps)})")
        for x in comps[:14]:
            nm, lid = x["league"]["name"], x["league"]["id"]
            cov = coverage(nm, country, odds_titles)
            marks = ("FD " if cov["football_data"] else "-- ") + \
                    ("TSD " if cov["thesportsdb"] else "--- ") + \
                    ("ODDS" if cov["odds_api"] else "----")
            full = all(cov.values())
            ready += full
            seasons = [s["year"] for s in x.get("seasons", [])]
            span = f"{min(seasons)}-{max(seasons)}" if seasons else "?"
            print(f"    id={lid:<5} {nm[:38]:<38} {x['league']['type']:<7}"
                  f" {marks}  {span}{'  <-- ALL THREE' if full else ''}")
        if len(comps) > 14:
            print(f"    ... and {len(comps)-14} more")

    print("\n" + "=" * 96)
    print(f"Competitions carried by ALL THREE sources: {ready}")
    print("Everything else is missing at least one leg and cannot produce a")
    print("board row. History alone is not enough; nor is odds alone.")


if __name__ == "__main__":
    main()
