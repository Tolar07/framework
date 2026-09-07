"""
API-Football (api-sports.io) client for OLP XDV.

Gives the framework a genuine structured source for fixtures + odds, using
the Architect's paid key -- no scraping, no JS-rendering, proper JSON API.
Intended to slot in as a second/third source alongside FlashScore/BBC/
SportyBet, feeding fixture_matcher.match_fixtures().

Docs: https://www.api-football.com/documentation-v3

IMPORTANT -- things this file deliberately does NOT guess:
- Your actual plan tier (Ultra/Mega/etc) and its rate limit. Check your
  dashboard at dashboard.api-football.com before relying on this in a live
  run; the retry/backoff below is generic, not tuned to your specific quota.
- League IDs for your five deploy leagues. API-Football uses its own
  internal IDs, unrelated to SportyBet's or Football-Data.co.uk's. The
  placeholders below are None on purpose -- do NOT fill them from memory.
  Run `python apifootball_client.py --list-leagues "Scottish Premiership"`
  (see bottom of file) against your real key to get the real IDs, once,
  then hardcode them.
"""

import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

import requests

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
API_KEY_ENV_VAR = "APIFOOTBALL_KEY"  # set in environment; never hardcode the key
API_KEY_ENV_VAR_ALT = "API_FOOTBALL_KEY"  # alternative name used in some .env files

# Fill these in once you've confirmed the real IDs against your own key --
# see the --list-leagues helper at the bottom of this file.
# Confirmed IDs from API-Football (API-Sports.io)
LEAGUE_ID_MAP = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Belgian Pro League": 144,
    "Scottish Premiership": 180,
    "Swiss Super League": 189,
    "Turkish Super Lig": 203,
    "Danish Superliga": 119,
    "Ekstraklasa": 106,
}


class APIFootballError(Exception):
    pass


@dataclass
class Fixture:
    source: str
    fixture_id: str
    home: str
    away: str
    kickoff_utc: str  # ISO 8601, as returned by API-Football
    league: str
    status: str
    raw: dict


class APIFootballClient:
    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key or os.environ.get(API_KEY_ENV_VAR) or os.environ.get(API_KEY_ENV_VAR_ALT)
        if not self.api_key:
            raise APIFootballError(
                f"No API-Football key found. Set {API_KEY_ENV_VAR} or {API_KEY_ENV_VAR_ALT} in the "
                "environment -- never hardcode the key in source or commit it."
            )
        self.session = session or requests.Session()
        self.session.headers.update({"x-apisports-key": self.api_key})

    def _get(self, path: str, params: dict, retries: int = 2, backoff: float = 1.5) -> dict:
        url = f"{API_FOOTBALL_BASE}{path}"
        last_exc = None
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=10)
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(backoff * (attempt + 1))
                continue

            if resp.status_code == 429:
                # Rate limited -- back off and retry rather than treating
                # this as "zero results" (the exact silent-failure mode
                # flagged in the 2026-09-06 diagnostic).
                time.sleep(backoff * (attempt + 2))
                continue
            if resp.status_code != 200:
                raise APIFootballError(f"{path} returned HTTP {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            if data.get("errors"):
                # API-Football often returns HTTP 200 with an "errors" object
                # on quota/plan/parameter problems. Surface it as a real
                # error -- don't let it look like a legitimate empty result.
                raise APIFootballError(f"{path} API-level error: {data['errors']}")
            return data

        raise APIFootballError(f"{path} failed after {retries} retries: {last_exc}")

    def get_fixtures(self, date: Optional[str], league_id: Optional[int] = None,
                      season: Optional[int] = None) -> list:
        """date: 'YYYY-MM-DD', or None for a season-wide pull (requires
        league_id + season together -- API-Football rejects an unbounded
        query with neither a date nor a league+season pair). Pass league_id
        whenever you have it -- pulling without it is a much heavier, slower
        call and more likely to hit rate limits."""
        params = {}
        if date is not None:
            params["date"] = date
        elif league_id is None or season is None:
            raise APIFootballError(
                "get_fixtures needs either a date, or both league_id and "
                "season for a season-wide pull -- refusing to send an "
                "unbounded query."
            )
        if league_id is not None:
            params["league"] = league_id
        if season is not None:
            params["season"] = season

        data = self._get("/fixtures", params)
        fixtures = []
        for item in data.get("response", []):
            fx, teams, league = item["fixture"], item["teams"], item["league"]
            fixtures.append(Fixture(
                source="api_football",
                fixture_id=str(fx["id"]),
                home=teams["home"]["name"],
                away=teams["away"]["name"],
                kickoff_utc=fx["date"],
                league=league["name"],
                status=fx["status"]["short"],
                raw=item,
            ))
        return fixtures

    def get_season_fixtures(self, league_id: int, season: int) -> list:
        """Pull the ENTIRE season's fixture calendar for one league in a
        single call -- no date param needed. Use this once (or periodically,
        to catch postponements/reschedules) to build a season-long fixture
        cache, rather than rediscovering fixtures from scratch every day.
        Daily runs then only need to confirm/enhance what the calendar
        already knows about, which is a much smaller and more resilient
        task than full same-day discovery across scrapers."""
        return self.get_fixtures(date=None, league_id=league_id, season=season)

    def get_odds(self, fixture_id: str) -> Optional[dict]:
        """Pre-match odds across multiple bookmakers -- this endpoint alone
        can partially cross-verify since it aggregates several books. Returns
        None (not {}) when odds genuinely aren't posted yet; callers must not
        treat that as a fetch failure."""
        data = self._get("/odds", {"fixture": fixture_id})
        response = data.get("response", [])
        return response[0] if response else None

    def get_live_odds(self, fixture_id: str) -> Optional[dict]:
        data = self._get("/odds/live", {"fixture": fixture_id})
        response = data.get("response", [])
        return response[0] if response else None

    def get_competitions_bulk(
        self,
        competitions: list,
        season: int,
        pause_seconds: float = 1.2,
    ) -> dict:
        """
        Loop get_season_fixtures across many competitions in one call --
        the practical way to "capture all teams/leagues/cups on the approve
        list" without hand-writing a loop each time.

        `competitions` is a list of dicts, each:
            {"name": str, "league_id": int, "type": "league" | "cup",
             "ratified": bool}
        You supply `type` and `ratified` explicitly -- this function does
        NOT infer them, because whether a competition is deploy-eligible is
        an Architect decision (per ID404/HR52), not something a fetch
        function should decide on your behalf.

        Returns:
            {
              "leagues": {name: [Fixture, ...], ...},
              "cups": {name: [Fixture, ...], ...},
              "unratified": {name: [Fixture, ...], ...},   # captured, held back
              "errors": {name: str, ...},                  # fetch failures
            }

        Cups get a note in the return, not special fetch logic: a cup's
        later rounds won't exist yet until earlier rounds are drawn, so
        whatever this returns for a cup is "current state," not "full
        season" the way a league fixture list is. Re-run periodically for
        cups specifically if you need later rounds as they're scheduled.

        `ratified=False` entries land in "unratified" regardless of
        type -- captured for intel/build purposes, but kept structurally
        separate so a season-calendar fetch can never quietly become
        deploy-eligible data. Promote a competition out of "unratified"
        only after an explicit Architect decision, by flipping the flag
        you pass in -- not by editing this function.
        """
        result = {"leagues": {}, "cups": {}, "unratified": {}, "errors": {}}

        for comp in competitions:
            name = comp["name"]
            try:
                fixtures = self.get_season_fixtures(comp["league_id"], season)
            except APIFootballError as exc:
                result["errors"][name] = str(exc)
                continue

            if not comp.get("ratified", False):
                result["unratified"][name] = fixtures
            elif comp.get("type") == "cup":
                result["cups"][name] = fixtures
            else:
                result["leagues"][name] = fixtures

            # Rate-limit courtesy pause -- bulk season pulls are heavier than
            # single-date calls; don't hammer 60 competitions back-to-back
            # without knowing your plan's actual per-minute cap.
            time.sleep(pause_seconds)

        return result

    def list_leagues(self, search: str) -> list:
        """One-off helper to find your real league IDs. Run this once per
        deploy league, record the ID in LEAGUE_ID_MAP above, done."""
        data = self._get("/leagues", {"search": search})
        return [
            {"id": item["league"]["id"], "name": item["league"]["name"],
             "country": item["country"]["name"]}
            for item in data.get("response", [])
        ]


if __name__ == "__main__":
    # Usage: APIFOOTBALL_KEY=xxx python apifootball_client.py "Scottish Premiership"
    if len(sys.argv) < 2:
        print("Usage: python apifootball_client.py \"<league search term>\"")
        sys.exit(1)
    client = APIFootballClient()
    for league in client.list_leagues(sys.argv[1]):
        print(league)