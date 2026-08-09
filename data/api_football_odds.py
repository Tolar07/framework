"""
API-Football live odds — a free fallback for The Odds API.

WHY THIS EXISTS
  The Odds API free tier is 500 requests/month and resets monthly. When it is
  exhausted (as at 2026-08-08: 496/500 used), every deploy league degrades to
  NO DATA — PENDING and the Phase 2 paper log cannot fill itself, so the
  Phase 3 gate (>=30 legs with CLV) is unreachable until the reset. This module
  is the fallback: the API-Football key already in `.env` (free plan, 100
  requests/DAY) serves the SAME bookmakers — Bet365, Pinnacle, William Hill —
  with Match Winner (1X2) and Goals Over/Under (2.5) markets, so a deploy pull
  that The Odds API refuses can still be priced. Verified live 2026-08-08.

QUOTA — DIFFERENT SHAPE, SAME DISCIPLINE
  API-Football free is 100 requests/day with a BURST cap (x-ratelimit-limit,
  seen at 10). A single /odds?fixture=ID call costs 1 request, and a deploy
  pull needs one fixture-ID lookup per fixture. Five leagues x ~6 fixtures is
  ~30-35 requests/day — inside 100, but a burst of 10 must be paced. check_quota
  reads the response headers and refuses to START a league pull when the daily
  balance is low, so a scheduled run degrades to NO DATA — PENDING rather than
  silently dying mid-day (mirroring pipeline/odds.py's floor discipline).

HR35
  A price that isn't quoted is None and is reported as NO DATA — PENDING.
  Team names that don't resolve through pipeline.odds.map_team pass through
  UNCHANGED so the caller reports NO DATA instead of guessing a match. The
  /fixtures feed is the single source of fixture IDs (no ID is invented).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source import SourceNoData
from data import fixtures_source
from data import retry as retry_module
from pipeline.odds import MarketQuote, FixtureOdds, map_team

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).parent / "cache" / "api_football_odds"

# A price is only fresh inside this window (matches pipeline/odds.py's 60-min
# ID403.1 V2 cap). Older than this it is REJECTED, not merely flagged.
ODDS_MAX_AGE_SECONDS = 60 * 60

# A fixture-ID LIST is schedule, not price: known ahead and stable intra-day,
# so it can be cached far longer than the prices built from it.
FIXTURES_MAX_AGE_SECONDS = 6 * 3600

# Refuse to spend the last of the day's allowance on a routine pull. Mirrors
# pipeline/odds.py QUOTA_FLOOR so an unattended job can't leave the day blind.
DAILY_FLOOR = 20

# The free plan also enforces a BURST cap: the API itself reports
# "Your rate limit is 10 requests per minute" (verified live 2026-08-08). A
# deploy pull makes one request per fixture, so consecutive requests must be
# paced to ~6s apart to stay inside the minute window, and a rate-limit signal
# must back off rather than abort the whole league.
BURST_PACE_SECONDS = 6.0
BURST_MAX_RETRIES = 3

# Deploy leagues only. The Odds API refuses on these; every other league stays
# on The Odds API (its richer multi-region feed is the primary). Scan-only
# leagues are never a capital pick, so pricing them via fallback is not needed.
DEPLOY_LEAGUES = ("Eredivisie", "Danish Superliga", "Belgian Pro League",
                  "Scottish Premiership", "Ekstraklasa")

# Bookmakers the Architect can actually reach, in preference order — the same
# principle as pipeline/odds.BOOKMAKER_PRIORITY but in API-Football's own names.
BOOKMAKER_PRIORITY = ("Bet365", "Pinnacle", "William Hill", "10Bet",
                      "Marathonbet", "bet365", "pinnacle")


class QuotaExhausted(SourceNoData):
    """Raised rather than silently returning an empty board.

    A deliberate daily guard (100 req/day), NOT a transient outage — so it must
    not trip a circuit breaker. Subclassing SourceNoData makes a multi-source
    caller fall through without recording a failure."""


class _DateWindowError(Exception):
    """The free plan refuses this date (serves only today-1 .. today+1)."""


def _key() -> str:
    k = os.environ.get("API_FOOTBALL_KEY")
    if not k:
        raise RuntimeError(
            "API_FOOTBALL_KEY not set. Free key at https://www.api-football.com/ "
            "— put it in .env (gitignored).")
    return k


def _headers() -> dict:
    return {"x-apisports-key": _key()}


def check_quota() -> tuple[int, int]:
    """(used_today, remaining_today) from the /status endpoint.

    Listing /status is cheap and is the same call pipeline/odds.check_quota
    makes for its own quota — a free probe, not a priced pull."""
    if requests is None:
        raise RuntimeError("requests not installed")
    r = retry_module.get_protected(f"{API_BASE}/status", breaker_name="api_football",
                                   headers=_headers(), timeout=25)
    req = r.json().get("response", {}).get("requests", {})
    used = int(req.get("current", 0))
    limit = int(req.get("limit_day", 100))
    return used, max(0, limit - used)


# ---------------------------------------------------------------------------
# Caching (mirrors pipeline/odds.py shape: fetch → cache → parse)
# ---------------------------------------------------------------------------

def _odds_cache_path(fixture_id: int) -> Path:
    return CACHE_DIR / f"odds_{fixture_id}.json"


def _read_odds_cache(fixture_id: int) -> Optional[dict]:
    p = _odds_cache_path(fixture_id)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - blob.get("fetched_at", 0) > ODDS_MAX_AGE_SECONDS:
        return None  # stale price REJECTED, not served (ID403.1 V2)
    return blob


def _write_odds_cache(fixture_id: int, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    blob = {"fetched_at": time.time(), "payload": payload}
    _odds_cache_path(fixture_id).write_text(
        json.dumps(blob), encoding="utf-8")


def _read_fixture_ids(league: str, day: date) -> Optional[dict]:
    p = CACHE_DIR / f"ids_{league.replace(' ', '_')}_{day.isoformat()}.json"
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - blob.get("fetched_at", 0) > FIXTURES_MAX_AGE_SECONDS:
        return None
    return blob


def _write_fixture_ids(league: str, day: date, pairs: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / f"ids_{league.replace(' ', '_')}_{day.isoformat()}.json"
    p.write_text(json.dumps({"fetched_at": time.time(), "fixtures": pairs}),
                 encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture-ID resolution (via /fixtures?date=, free-plan compatible)
# ---------------------------------------------------------------------------

def _fixture_ids_for_day(league: str, day: date,
                         use_cache: bool = True,
                         ensure_quota=None) -> dict:
    """API-Football fixture metadata for ONE league on ONE date.

    Returns {fixture_id: {"home": raw_name, "away": raw_name, "date": iso}}.
    The free plan refuses season-scoped queries, but the date feed is open.
    We resolve the league's ID once (fixtures_source.resolve_league_id) and
    filter the day's feed to that league. No ID or team name is invented —
    HR35. The /odds response carries bookmakers only (no team names), so the
    teams are captured HERE, from the fixtures feed, and carried alongside.
    `ensure_quota` (a zero-arg callable) is invoked before the network pull,
    so the daily floor is checked only when a request is actually about to
    be spent — never for a cache hit."""
    cached = _read_fixture_ids(league, day) if use_cache else None
    if cached is not None:
        return cached.get("fixtures", {})
    if requests is None:
        raise RuntimeError("requests not installed")
    if ensure_quota is not None:
        ensure_quota()  # about to spend a request — confirm the floor holds
    league_id = fixtures_source.resolve_league_id(league)
    r = _burst_get(f"{API_BASE}/fixtures", {"date": day.isoformat()})
    r.raise_for_status()
    payload = r.json()
    if payload.get("errors"):
        # Free plan serves a tight date window (today-1 .. today+1). Out-of-
        # window dates are REFUSED with a plan error — not a transient failure.
        # Callers treat this as "no fixtures available this date on the free
        # plan" (a flag), never as a data-source outage. HR35: no guessing.
        raise _DateWindowError(day, str(payload["errors"]))
    pairs: dict = {}
    for item in payload.get("response", []):
        if item.get("league", {}).get("id") != league_id:
            continue
        fid = item.get("fixture", {}).get("id")
        teams = item.get("teams", {})
        home = teams.get("home", {}).get("name")
        away = teams.get("away", {}).get("name")
        if not fid or not home or not away:
            continue  # HR35 — incomplete record, skipped not guessed
        pairs[str(fid)] = {
            "home": home.strip(),
            "away": away.strip(),
            "date": item.get("fixture", {}).get("date", ""),
        }
    _write_fixture_ids(league, day, pairs)
    return pairs


# ---------------------------------------------------------------------------
# Odds parsing — API-Football market shape → FixtureOdds contract
# ---------------------------------------------------------------------------

def _pick_price(bookmakers: list[dict], market_name: str,
                outcome_name: str, point: Optional[float] = None
                ) -> MarketQuote:
    """Best price for one outcome across books, in Architect-priority order.

    API-Football nests outcomes as {value: "Over 2.5", odd: 1.44} and points
    (Asian lines) as {value: "Over 2.5", point: 2.5}. If no book in priority
    quotes it, falls back to the best price across all books and marks n_books
    so an outlier stays visible. Mirrors pipeline/odds._best_price."""
    def _book_price(name: str) -> Optional[float]:
        """Price this book quotes for the outcome, else None (HR35 — a bad or
        missing price is None, never guessed)."""
        for bm in bookmakers:
            if bm.get("name", "") != name:
                continue
            for m in bm.get("bets", []):
                if m.get("name") != market_name:
                    continue
                for v in m.get("values", []):
                    if v.get("value", "") != outcome_name:
                        continue
                    if point is not None and v.get("point") != point:
                        continue
                    odd = v.get("odd")
                    try:
                        odd_f = float(odd)
                    except (TypeError, ValueError):
                        return None  # non-numeric never counts
                    if odd_f <= 1.0:
                        return None  # degenerate never counts
                    return odd_f
        return None

    # Priority books FIRST, in the Architect's reachable order. The API lists
    # books arbitrarily (10Bet before Bet365), so payload order must not decide.
    for name in BOOKMAKER_PRIORITY:
        p = _book_price(name)
        if p is not None:
            return MarketQuote(price=p, bookmaker=name, n_books=1,
                               captured_at=_now_iso())

    # No reachable book quotes it — best price across ALL books, provenance
    # marked so an outlier stays visible (mirrors pipeline/odds._best_price).
    fallback: Optional[float] = None
    n_books = 0
    for bm in bookmakers:
        for m in bm.get("bets", []):
            if m.get("name") != market_name:
                continue
            for v in m.get("values", []):
                if v.get("value", "") != outcome_name:
                    continue
                if point is not None and v.get("point") != point:
                    continue
                odd = v.get("odd")
                try:
                    odd_f = float(odd)
                except (TypeError, ValueError):
                    continue
                if odd_f <= 1.0:
                    continue
                n_books += 1
                if fallback is None or odd_f < fallback:
                    fallback = odd_f
    if fallback is None:
        return MarketQuote()
    return MarketQuote(price=fallback, bookmaker="best-of-all", n_books=n_books,
                       captured_at=_now_iso())


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


_last_request_at: float = 0.0  # module-level pacing gate shared by all requests


def _pace() -> None:
    """Sleep so consecutive requests stay >= BURST_PACE_SECONDS apart."""
    global _last_request_at
    elapsed = time.time() - _last_request_at
    if _last_request_at and elapsed < BURST_PACE_SECONDS:
        time.sleep(BURST_PACE_SECONDS - elapsed)


def _burst_get(url: str, params: dict) -> requests.Response:
    """GET with burst-cap pacing, Retry-After backoff on 429, and a circuit
    breaker so repeated failures degrade to NO DATA — PENDING instead of
    hammering the quota.

    The free plan rate limit is 10 requests/minute (its own words), so every
    request — fixture lookup or odds — waits on the shared pace gate. On a 429
    we honour Retry-After (or the pace constant) up to BURST_MAX_RETRIES before
    giving up. A 429 is a pacing signal, not a permanent failure."""
    global _last_request_at
    breaker = retry_module.get_breaker("api_football")
    if not breaker.allow_request():
        raise RuntimeError("api_football circuit breaker OPEN — quota in jeopardy, "
                           "degrade to NO DATA — PENDING")
    _pace()
    for attempt in range(BURST_MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=_headers(), params=params, timeout=30)
            _last_request_at = time.time()
            if r.status_code == 429:
                breaker.record_failure()
            else:
                breaker.record_success()
            if r.status_code != 429:
                return r
            if attempt >= BURST_MAX_RETRIES:
                break
            wait = float(r.headers.get("Retry-After", BURST_PACE_SECONDS * 2))
            time.sleep(max(wait, BURST_PACE_SECONDS))
        except (requests.RequestException, OSError) as e:
            breaker.record_failure()
            if attempt >= BURST_MAX_RETRIES:
                raise
            time.sleep(BURST_PACE_SECONDS)
    return r  # last attempt's 429 — caller raises


def _parse_odds_payload(league: str, payload: dict, meta: dict) -> FixtureOdds:
    """One /odds?fixture= response + its fixtures-feed metadata → FixtureOdds.

    The /odds response carries bookmakers only — team names come from the
    /fixtures feed (captured alongside the fixture IDs) and are passed in as
    `meta`. Names resolve through pipeline.odds.map_team so the board joins
    them onto its own fixtures the same way it joins The Odds API prices. A
    team name that maps to nothing passes through unchanged → the caller sees
    NO DATA — PENDING, never a guessed fixture (HR35)."""
    item = (payload.get("response") or [{}])[0]
    home_raw = meta.get("home")
    away_raw = meta.get("away")
    if not home_raw or not away_raw:
        raise SourceNoData(f"api-football: incomplete fixture record for {league}")
    home = map_team(league, home_raw.strip())
    away = map_team(league, away_raw.strip())
    bookmakers = item.get("bookmakers", [])
    out = FixtureOdds(
        league=league,
        home_team=home,
        away_team=away,
        kickoff_utc=meta.get("date", ""),
        home=_pick_price(bookmakers, "Match Winner", "Home"),
        draw=_pick_price(bookmakers, "Match Winner", "Draw"),
        away=_pick_price(bookmakers, "Match Winner", "Away"),
        over25=_pick_price(bookmakers, "Goals Over/Under", "Over 2.5"),
        under25=_pick_price(bookmakers, "Goals Over/Under", "Under 2.5"),
        source="api-football.com (free plan)",
        source_tier="T1",
    )
    if not out.over25.available:
        out.notes.append("Over/Under 2.5 not quoted — NO DATA — PENDING")
    if not out.home.available and not out.away.available:
        out.notes.append("1X2 not quoted — NO DATA — PENDING")
    return out


# ---------------------------------------------------------------------------
# Public fetch — same contract as pipeline/odds.fetch_odds
# ---------------------------------------------------------------------------

def fetch_odds(league: str, days_ahead: int = 3,
               use_cache: bool = True) -> tuple[list[FixtureOdds], list[str]]:
    """Free-plan prices for one league over the next `days_ahead` days.

    Returns (fixtures, flags). Raises QuotaExhausted rather than quietly
    returning nothing, so a caller can degrade to NO DATA — PENDING honestly.
    Callers are pipeline/odds.fetch_odds (the fallback) and the multi-source
    odds layer; both already catch QuotaExhausted by class."""
    flags: list[str] = []
    if league not in DEPLOY_LEAGUES:
        raise SourceNoData(f"'{league}' has no API-Football odds fallback "
                           f"(deploy leagues only)")
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch odds")

    # Quota guards NETWORK pulls only. Cached prices cost zero requests, so
    # they are served even at the floor (mirrors pipeline/odds.py, which reads
    # its cache before touching quota). A pull that can be served entirely from
    # cache must not be refused because the day is otherwise spent.
    _quota_checked: list[bool] = []

    def _ensure_quota() -> None:
        # The /status probe itself counts against the daily budget, so probe
        # ONCE, at the first network need — not per fixture.
        if not _quota_checked:
            _quota_checked.append(True)
            used, remaining = check_quota()
            if remaining < DAILY_FLOOR:
                raise QuotaExhausted(
                    f"API-Football daily quota down to {remaining} "
                    f"(floor {DAILY_FLOOR}). Refusing to spend it on a routine "
                    f"pull — prices are NO DATA — PENDING rather than exhausting "
                    f"the day.")

    out: list[FixtureOdds] = []
    today = date.today()
    # Free plan serves only today-1 .. today+1 (verified live 2026-08-08). A
    # day outside the window would be refused by the API — skip it before the
    # request, so a doomed pull never wastes a burst slot.
    for offset in range(days_ahead + 1):
        day = today + timedelta(days=offset)
        if day > today + timedelta(days=1):
            flags.append(f"{league}: api-football free plan serves only "
                         f"today±1 — {day.isoformat()} skipped")
            continue
        try:
            # May hit the network for the fixture-ID feed — gate that pull.
            meta = _fixture_ids_for_day(league, day, use_cache=use_cache,
                                        ensure_quota=_ensure_quota)
        except _DateWindowError as e:
            flags.append(f"{league}: api-football free plan has no access to "
                         f"{day.isoformat()} (window is today±1) — skipping")
            continue
        for idx, (fid_str, meta) in enumerate(meta.items()):
            fid = int(fid_str)
            if use_cache:
                blob = _read_odds_cache(fid)
                if blob is not None:
                    out.append(_parse_odds_payload(league, blob["payload"], meta))
                    continue
            _ensure_quota()  # about to spend a request — confirm the floor holds
            if idx > 0:
                time.sleep(BURST_PACE_SECONDS)  # stay inside the burst window
            r = _burst_get(f"{API_BASE}/odds", {"fixture": fid})
            if r.status_code == 429:
                flags.append(f"{league}: api-football burst cap hit — "
                             f"{len(out)} fixture(s) priced, rest NO DATA")
                break
            r.raise_for_status()
            payload = r.json()
            if payload.get("errors"):
                if "rateLimit" in payload["errors"]:
                    # The 10/min burst window — stop pricing, keep what we have.
                    flags.append(f"{league}: api-football rate limit — "
                                 f"{len(out)} fixture(s) priced, rest NO DATA")
                    break
                flags.append(f"{league}: api-football odds error for fixture "
                             f"{fid} ({payload['errors']}) — NO DATA — PENDING")
                continue
            if not payload.get("response"):
                continue  # no odds yet for this fixture — not an error
            _write_odds_cache(fid, payload)
            out.append(_parse_odds_payload(league, payload, meta))
    if not out:
        flags.append(f"{league}: api-football returned no priced fixtures "
                     f"in the next {days_ahead} day(s)")
    else:
        flags.append(f"{league}: odds served from api-football free plan "
                     f"({len(out)} fixture(s))")
    return out, flags
