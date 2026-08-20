"""
Upcoming-fixtures source via ESPN's public scoreboard API (site.api.espn.com).

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

from data.thesportsdb_fixtures import UpcomingFixture, map_team
from data.retry import get

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "espn"
# Fixtures for a given day are known well ahead and rarely change intra-day, so
# a half-day TTL is safe — the same reasoning as the TheSportsDB fixture cache.
# A reschedule is caught within the TTL window, which is acceptable for a daily
# board.
FIXTURES_MAX_AGE_SECONDS = 6 * 3600

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
    "Europa League": "uefa.europa",
    "Conference League": "uefa.conf",
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
    from time import time
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


def _fetch_day(league: str, slug: str, day: str) -> list[dict]:
    """One day's raw events for a league, cached 6h per (league, day)."""
    path = _cache_path(league, day)
    cached = _read_cache(path)
    if cached is not None:
        return cached
    if requests is None:
        raise RuntimeError("espn_source: the 'requests' library is required")
    url = f"{API_BASE}/{slug}/scoreboard"
    resp = get(url, params={"dates": day}, timeout=25)
    events = (resp.json().get("events") or []) if resp.json() else []
    _write_cache(path, events)
    return events


def fetch_upcoming(league: str, fixtures_season: str, days_ahead: int = 14
                   ) -> tuple[list[UpcomingFixture], list[dict]]:
    """Returns (fixtures, skipped) for not-yet-played matches inside the next
    `days_ahead` days, per league. Raises ValueError for a league with no
    verified slug (HR35: a wrong slug silently returns another competition's
    fixtures). Per-row problems become `skipped` entries, never guessed values.

    `fixtures_season` is accepted for signature compatibility with the other
    providers but is irrelevant here — ESPN's scoreboard endpoint is dated, not
    seasoned, so the window is fetched day-by-day."""
    if requests is None:
        raise RuntimeError("espn_source: the 'requests' library is required")
    slug = SLUGS.get(league)
    if not slug:
        raise ValueError(f"'{league}' is not mapped in espn_source.SLUGS "
                         f"(no verified ESPN slug — honest gap, HR35).")

    fixtures: list[UpcomingFixture] = []
    seen: set[tuple[str, str, str]] = set()
    skipped: list[dict] = []

    today = date.today()
    for offset in range(days_ahead + 1):
        day = today + timedelta(days=offset)
        try:
            events = _fetch_day(league, slug, day.isoformat().replace("-", ""))
        except Exception as e:  # one day's failure must not kill the window
            skipped.append({"reason": f"{type(e).__name__}: {str(e)[:120]}",
                            "day": day.isoformat()})
            continue
        for ev in events or []:
            status = ((ev.get("status") or {}).get("type") or {}).get("name") or ""
            if status not in UPCOMING_STATUSES:
                continue  # a result or a never-played match — not upcoming
            comps = (ev.get("competitions") or [{}])[0].get("competitors") or []
            home = away = ""
            for c in comps:
                name = ((c.get("team") or {}).get("displayName") or "").strip()
                if not name:
                    continue
                if c.get("homeAway") == "home":
                    home = name
                elif c.get("homeAway") == "away":
                    away = name
            if not home or not away:
                skipped.append({"reason": "missing team name", "day": day.isoformat()})
                continue  # HR35: no team name -> drop, never reconstruct
            kickoff = (ev.get("date") or "").strip()
            if not kickoff:
                skipped.append({"reason": "missing kickoff date",
                                "fixture": f"{home} v {away}"})
                continue  # HR35: no date -> drop (a leg needs a settle date)
            key = (home, away, day.isoformat())
            if key in seen:
                continue  # a match spanned two day fetches / duplicate event
            seen.add(key)
            fixtures.append(UpcomingFixture(
                league=league,
                date=day.isoformat(),
                home_team=map_team(league, home),
                away_team=map_team(league, away),
                kickoff_utc=kickoff,
                source="espn.com",
            ))
    return fixtures, skipped


def as_pairs(fixtures: list[UpcomingFixture]) -> list[tuple[str, str]]:
    """Adapter for orchestrator.scan_one_league()'s upcoming_fixtures argument."""
    return [(f.home_team, f.away_team) for f in fixtures]
