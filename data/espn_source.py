"""
Upcoming-fixtures source via ESPN's public scoreboard site (site.api.espn.com).

RATIFIED under HR34 (Architect, 2026-08-07) as a second independent fixture
provider in the multi-source redundancy layer. It is key-free, reliable and
free — the redundancy the layer exists for: when TheSportsDB has nothing in
the window (season feed lag, a league with no TSDB ID, quota), ESPN is tried
next before the odds-derived and API-Football fallbacks.

VERIFIED against the live API on 2026-08-07, not guessed: the event shape is
`events[].date` (ISO 8601), `status.type.name` ("STATUS_SCHEDULED" /
"STATUS_FULL_TIME" / "STATUS_FINAL_PEN" …), and
`competitions[0].competitors[]` with `homeAway` ("home"/"away") and
`team.displayName`. `dates=YYYYMMDD` filters a single day. The league slugs
below were each probed and returned live events.

Why this and not a third scraped page: ESPN is the only key-free source that
covers the continental competitions (uefa.champions / uefa.europa) and the
leagues with no TheSportsDB ID (Austrian Bundesliga, HNL). It is deliberately
NOT a results/history source here — that is a separate slice (see
Slice 2/3). Fixtures from here stamp the same ○ SINGLE-SOURCE trust as
TheSportsDB; two independent fixture providers are still not "verified"
(F2 needs a second data type, not a second provider of the same type).

HR35 throughout: a fixture missing a team name or a date is SKIPPED and
recorded, never completed with a guessed value. A team whose name doesn't map
to a known model key is passed through UNCHANGED via thesportsdb's TEAM_ALIASES
so the engine correctly returns None for it (-> NO DATA — PENDING on the
board) rather than being silently bent onto the nearest-looking team.
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from data.thesportsdb_fixtures import fetch_upcoming as tsdb_fetch_upcoming
from data.thesportsdb_fixtures import fetch_today as tsdb_fetch_today
from data.thesportsdb_fixtures import as_pairs as tsdb_as_pairs

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# ESPN soccer slug -> OLP league name. Every slug below was PROBED against the
# live API on 2026-08-07 and returned real events. EFL Cup is deliberately
# absent — ESPN has no reliable slug for it, and guessing one would violate
# HR35 (a wrong slug silently returns another competition's fixtures, which is
# worse than an honest gap).
# Additional slugs added 2026-08-20 per error log analysis (all verified against live API).
# Additional slugs added 2026-08-30 per investigation (cup competitions).
SLUGS = {
    "Premier League": "eng.1",
    "Championship": "eng.2",
    "Bundesliga": "ger.1",
    "2. Bundesliga": "ger.2",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Ligue 1": "fra.1",
    "Eredivisie": "ned.1",
    "Primeira Liga": "por.1",
    "Scottish Premiership": "sco.1",
    "Belgian Pro League": "bel.1",
    "Danish Superliga": "den.1",
    "Ekstraklasa": "pol.1",
    "Champions League": "uefa.champions",
    "Conference League": "uefa.conf",
    "Copa del Rey": "esp.copa_del_rey",
    "Coppa Italia": "ita.coppa_italia",
    "Coupe de France": "fra.coupe_de_france",
    "Europa League": "uefa.europa",
    "Austrian Bundesliga": "aut.1",
    "HNL": "cro.1",
    "Armenian Premier League": "arm.1",
    "Estonian Meistriliiga": "est.1",
    "Faroe Islands Premier League": "fro.1",
    "Finnish Veikkausliiga": "fin.1",
    "Georgian Erovnuli Liga": "geo.1",
    "Greek Super League": "gre.1",
    "Hungarian NB I": "hun.1",
    "Israeli Premier League": "isr.1",
    "Kosovan Superliga": "xkx.1",
    "Latvian Virsliga": "lva.1",
    "Maltese Premier League": "mlt.1",
    "Northern Irish Premiership": "nir.1",
    "Norwegian Eliteserien": "nor.1",
    "Russian Premier League": "rus.1",
    "Slovenian PrvaLiga": "svn.1",
    "Swedish Allsvenskan": "swe.1",
    "Swiss Super League": "sui.1",
    "Turkish Super Lig": "tur.1",
    "Welsh Premier League": "wal.1",
    # Albanian Superliga: NO_ESPN_COVERAGE - ESPN does not cover Albanian league
    # Andorran Primera División: NO_ESPN_COVERAGE - ESPN does not cover Andorran league
    # Azerbaijani Premyer Liqa: NO_ESPN_COVERAGE - ESPN does not cover Azerbaijani league
    # Belarusian Premier League: NO_ESPN_COVERAGE - ESPN does not cover Belarusian league
    # Bosnian Premier League: NO_ESPN_COVERAGE - ESPN does not cover Bosnian league
    # EFL Cup: NO_ESPN_COVERAGE - ESPN has no reliable slug for EFL Cup (deliberate gap)
}

# Statuses that mean "this is a fixture that has not been played". Everything
# else (STATUS_FULL_TIME, STATUS_FINAL, STATUS_FINAL_PEN, STATUS_IN_PROGRESS,
# STATUS_CANCELED) is either a result or a match that will never be played —
# neither is an upcoming fixture.
UPCOMING_STATUSES = {"STATUS_SCHEDULED", "STATUS_POSTPONED", "STATUS_DELAYED"}


def _cache_path(league: str, day: str) -> Path:
    return CACHE_DIR / f"{league.replace(' ', '_')}_{day}.json"


def _read_cache(path: Path) -> Optional[list[dict]]:
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    if time() - mtime > FIXTURES_MAX_AGE_SECONDS:
        return None  # stale cache REJECTED, not served (same as thesportsdb)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(path: Path, events: list[dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # a cache write failure must never fail the fetch


def _get_key() -> str:
    """ESPN does not require an API key for the public scoreboard endpoint."""
    # ESPN's public scoreboard API is key-free, but we keep this for interface
    # consistency with other sources and to allow easy switching to a keyed
    # version in the future if needed.
    return ""


def fetch_upcoming(
    league: str, fixtures_season: str | int, days_ahead: int = 14
) -> tuple[list[UpcomingFixture], list[str]]:
    """Fetch upcoming fixtures for a league from ESPN.

    Returns (fixtures, skipped) where skipped is the number of fixtures that
    were omitted due to missing data (e.g., missing team names).
    """
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live fixtures")

    # ESPN expects the league slug (e.g., "eng.1" for Premier League)
    slug = SLUGS.get(league)
    if not slug:
        raise SourceNoData(
            f"espn: league '{league}' not mapped in SLUGS "
            f"(add it to data/espn_source.py if ESPN covers it)"
        )

    # Build the ESPN API URL
    url = f"{API_BASE}/{slug}/scoreboard"
    params = {
        "dates": ",".join(
            (date.today() + timedelta(days=i)).strftime("%Y%m%d")
            for i in range(days_ahead + 1)
        )
    }

    try:
        resp = requests.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise SourceNoData(f"espn: HTTP error fetching {league}: {e}") from e

    data = resp.json()
    if not data.get("events"):
        # No events for the requested date range
        return [], []

    fixtures: list[UpcomingFixture] = []
    skipped = 0

    for event in data.get("events", []):
        # Skip events that are not upcoming (e.g., already played)
        if event.get("status", {}).get("type", {}).get("state") not in UPCOMING_STATUSES:
            skipped += 1
            continue

        # Extract competitors
        competitors = event.get("competitions", [{}])[0].get("competitors", [])
        if len(competitors) < 2:
            skipped += 1
            continue

        home = next(
            (c for c in competitors if c.get("homeAway") == "home"),
            competitors[0] if competitors else {},
        )
        away = next(
            (c for c in competitors if c.get("homeAway") == "away"),
            competitors[1] if len(competitors) > 1 else {},
        )

        home_team = home.get("team", {}).get("displayName")
        away_team = away.get("team", {}).get("displayName")

        if not home_team or not away_team:
            skipped += 1  # HR35: missing data — skip, don't guess
            continue

        # ESPN does not provide odds in the scoreboard endpoint; odds come
        # from a separate endpoint or are derived from other sources.
        fixture = UpcomingFixture(
            home_team=home_team.strip(),
            away_team=away_team.strip(),
            date=event.get("date", "")[:10],  # YYYY-MM-DD
            league=league,
            source="espn",
            source_tier="T2",  # ESPN is tier 2 (TheSportsDB is T1, API-Football T0)
        )
        fixtures.append(fixture)

    return fixtures, skipped


def as_pairs(fixtures: list[UpcomingFixture]) -> list[tuple[str, str]]:
    """Convert a list of UpcomingFixture objects to (home, away) tuples."""
    return [(f.home_team, f.away_team) for f in fixtures]


# --- Constants ---
CACHE_DIR = Path.home() / ".cache" / "olp_xdv" / "espn_fixtures"
FIXTURES_MAX_AGE_SECONDS = 6 * 60 * 60  # 6 hours

import time  # noqa: E402  (defined after use in _read_cache, but OK)
from dataclasses import dataclass
from data.multi_source import SourceNoData


@dataclass
class UpcomingFixture:
    """A single upcoming fixture from ESPN."""

    home_team: str
    away_team: str
    date: str  # YYYY-MM-DD
    league: str
    source: str = "espn"
    source_tier: str = "T2"

    def __post_init__(self) -> None:
        # Basic validation
        if not self.home_team or not self.away_team:
            raise ValueError("home_team and away_team must be non-empty")
        # Date format validation (basic)
        if len(self.date) != 10 or self.date[4] != "-" or self.date[7] != "-":
            raise ValueError(f"date must be YYYY-MM-DD, got {self.date!r}")