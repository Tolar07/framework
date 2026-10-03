"""
ESPN's public scoreboard — a free, keyless second source for fixtures and prices.

WHY (Architect 2026-10-03: no paid APIs)
  Every fixture on the board came from TheSportsDB alone, so ID403 stamped all
  of them ○ SINGLE-SOURCE: VERIFIED needs two independent T1/T2 sources. ESPN
  is T2 in the ID404 register (verification/id403.py SOURCE_TRUST) and lists
  the same matches, with kickoff time, status (scheduled / postponed /
  cancelled) and a DraftKings price line, at no cost.

VERIFIED AGAINST THE LIVE API on 2026-10-03, not guessed
  - One date per request: `scoreboard?dates=YYYYMMDD`. A range returns HTTP 400.
    The date is ESPN's (US) calendar day, so a UTC-date-d kickoff can sit on
    ESPN's d-1 — callers fetch d-1..d+1.
  - `events[].date` is ISO UTC ("2026-10-04T12:00Z"); `status.type.name` is
    STATUS_SCHEDULED / STATUS_POSTPONED / STATUS_CANCELED / STATUS_FULL_TIME …
  - `competitions[0].competitors[]` carries `homeAway` and `team.displayName`.
  - `competitions[0].odds[0]` is DraftKings: `moneyline.home/away.close.odds`,
    `drawOdds.moneyLine`, `total.over/under.close.odds` at `overUnder`, all
    American odds. Every listed event on the probe dates carried a line.
  - Every slug below is in ESPN's own league directory
    (sports.core.api.espn.com/v2/sports/soccer/leagues) and returned events.
    ESPN has NO Polish league, so Ekstraklasa is deliberately unmapped (a
    guessed slug answers HTTP 400).

HR35: a missing team name or date drops the event (never completed by guess);
a missing price is None, never interpolated. Responses are cached IN MEMORY for
one run (the price check and the fixture check ask for the same days); nothing
older than 60 minutes is served.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
except ImportError:  # pragma: no cover — requests is in requirements.txt
    requests = None  # type: ignore[assignment]

API_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
DOMAIN = "espn.com"
MAX_AGE_SECONDS = 60 * 60
_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}

# League name (as the board names it) -> ESPN slug. See the module docstring
# for how each was checked.
SLUGS = {
    "Premier League": "eng.1",
    "Championship": "eng.2",
    "League One": "eng.3",
    "League Two": "eng.4",
    "National League": "eng.5",
    "FA Cup": "eng.fa",
    "EFL Cup": "eng.league_cup",
    "Scottish Premiership": "sco.1",
    "La Liga": "esp.1",
    "La Liga 2": "esp.2",
    "Bundesliga": "ger.1",
    "2. Bundesliga": "ger.2",
    "Serie A": "ita.1",
    "Serie B": "ita.2",
    "Ligue 1": "fra.1",
    "Ligue 2": "fra.2",
    "Eredivisie": "ned.1",
    "Primeira Liga": "por.1",
    "Belgian Pro League": "bel.1",
    "Danish Superliga": "den.1",
    "UEFA Nations League": "uefa.nations",
    "Champions League": "uefa.champions",
    "Europa League": "uefa.europa",
    "Conference League": "uefa.europa.conf",
}

# ESPN statuses meaning the match will NOT be played as scheduled.
OFF_STATUSES = {
    "STATUS_POSTPONED": "POSTPONED",
    "STATUS_CANCELED": "CANCELLED",
    "STATUS_CANCELLED": "CANCELLED",
    "STATUS_SUSPENDED": "SUSPENDED",
    "STATUS_ABANDONED": "ABANDONED",
    "STATUS_FORFEIT": "FORFEITED",
}


@dataclass
class EspnEvent:
    league: str
    home: str
    away: str
    kickoff_utc: str           # ISO, e.g. "2026-10-04T12:00Z"
    status: str                # ESPN status.type.name
    url: str
    # DraftKings line as decimal odds (None where not quoted): home, draw,
    # away, over25, under25.
    prices: dict[str, Optional[float]] = field(default_factory=dict)
    provider: str = ""

    @property
    def day(self) -> str:
        return self.kickoff_utc[:10]

    @property
    def off(self) -> Optional[str]:
        """POSTPONED / CANCELLED / … when ESPN says it won't be played, else None."""
        return OFF_STATUSES.get(self.status)


def american_to_decimal(raw: object) -> Optional[float]:
    """'+160' -> 2.6, '-120' -> 1.833, 230 -> 3.3, 'EVEN' -> 2.0; None if unreadable."""
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if s in ("EVEN", "EV"):
        return 2.0
    try:
        v = float(s)
    except ValueError:
        return None
    if v == 0 or -100 < v < 100:
        return None
    return round(1 + (v / 100 if v > 0 else 100 / abs(v)), 4)


def _close(side: object) -> Optional[float]:
    if not isinstance(side, dict):
        return None
    for k in ("close", "current", "open"):
        leg = side.get(k)
        if isinstance(leg, dict) and leg.get("odds") is not None:
            return american_to_decimal(leg.get("odds"))
    return None


def _prices(comp: dict) -> tuple[dict[str, Optional[float]], str]:
    lines = comp.get("odds") or []
    if not lines or not isinstance(lines[0], dict):
        return {}, ""
    o = lines[0]
    ml = o.get("moneyline") or {}
    total = o.get("total") or {}
    draw = o.get("drawOdds") or {}
    prices: dict[str, Optional[float]] = {
        "home": _close(ml.get("home")),
        "draw": american_to_decimal(draw.get("moneyLine")),
        "away": _close(ml.get("away")),
        "over25": None,
        "under25": None,
    }
    raw_line = o.get("overUnder")
    try:
        line = float(raw_line) if raw_line is not None else None
    except (TypeError, ValueError):
        line = None
    if line == 2.5:
        prices["over25"] = _close(total.get("over"))
        prices["under25"] = _close(total.get("under"))
    provider = ((o.get("provider") or {}).get("name") or "").strip()
    return prices, provider


def parse_events(league: str, payload: dict) -> list[EspnEvent]:
    """EspnEvents from one scoreboard response. Events missing a team or a
    date are dropped (HR35), not completed."""
    out: list[EspnEvent] = []
    for ev in payload.get("events") or []:
        if not isinstance(ev, dict):
            continue
        comps = ev.get("competitions") or [{}]
        comp = comps[0] if isinstance(comps[0], dict) else {}
        teams = {c.get("homeAway"): ((c.get("team") or {}).get("displayName") or "").strip()
                 for c in comp.get("competitors") or [] if isinstance(c, dict)}
        home, away, when = teams.get("home"), teams.get("away"), (ev.get("date") or "").strip()
        if not home or not away or len(when) < 10:
            continue
        links = [str(x["href"]) for x in ev.get("links") or []
                 if isinstance(x, dict) and x.get("href")]
        prices, provider = _prices(comp)
        out.append(EspnEvent(
            league=league, home=home, away=away, kickoff_utc=when,
            status=((ev.get("status") or {}).get("type") or {}).get("name", ""),
            url=links[0] if links else f"https://www.{DOMAIN}/soccer/",
            prices=prices, provider=provider))
    return out


def fetch_day(league: str, day: str, timeout: float = 15.0) -> list[EspnEvent]:
    """Every ESPN event for `league` on ESPN's calendar day `day` (YYYY-MM-DD).

    Raises ValueError for a league ESPN doesn't cover and the request's own
    error for a failed fetch; the caller decides how to degrade."""
    slug = SLUGS.get(league)
    if not slug:
        raise ValueError(f"ESPN has no slug for {league!r}")
    hit = _CACHE.get((slug, day))
    if hit and time.time() - hit[0] <= MAX_AGE_SECONDS:
        return parse_events(league, hit[1])
    if requests is None:
        raise RuntimeError("requests not installed — cannot reach ESPN")
    r = requests.get(f"{API_BASE}/{slug}/scoreboard",
                     params={"dates": day.replace("-", "")},
                     headers={"User-Agent": "OLP-XDV/1.0"}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("ESPN returned no scoreboard object")
    _CACHE[(slug, day)] = (time.time(), data)
    return parse_events(league, data)
