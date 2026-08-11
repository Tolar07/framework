"""
Live entry odds via The Odds API (the-odds-api.com).

WHY THIS EXISTS
  HR46 requires an entry price AND a closing price per logged leg. Section 7.2
  ratified odds as ARCHITECT-FED because no readable live-odds source existed
  at the time — which meant the Phase 2 paper log could never fill itself, and
  the Phase 3 gate (>=30 legs with logged CLV) could never be reached without
  the Architect typing prices in every day. This module supplies that entry
  price automatically. It does NOT replace the Architect's judgement or his
  capital authority; it only removes the transcription step.

QUOTA — THE BINDING CONSTRAINT
  The free plan allows 500 requests/month, and a request costs
  (number of regions) x (number of markets). A single 'uk,eu' + 'h2h,totals'
  call therefore costs 4, and every whitelisted league once daily would burn
  ~600/month — over the cap. Defaults here are ONE region ('uk', where Bet365
  sits) and two markets, i.e. 2 credits per league per pull: about 300/month
  at ~15 priced leagues/day. `check_quota()` refuses to spend when the
  remaining balance is low, so a scheduled run degrades to NO DATA — PENDING
  rather than silently dying mid-month.

HR35
  A price that isn't quoted is None and is reported as NO DATA — PENDING.
  Nothing here interpolates, averages across bookmakers to invent a missing
  side, or carries a stale cached price forward past its freshness window
  (ID403.1 V2 caps odds recency at 60 minutes).
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source import SourceNoData
from data.retry import get_protected

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://api.the-odds-api.com/v4"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "odds"
FIXTURES_DIR = Path(__file__).parent.parent / "data" / "cache" / "fixtures_from_odds"

# ID403.1 V2: odds go stale at 60 minutes. A cached price older than this is
# REJECTED, not merely flagged.
ODDS_MAX_AGE_SECONDS = 60 * 60

# A fixture LIST derived from the odds feed is different from a price: the
# schedule for a given day is known ahead and does not change intra-day, so the
# derived list can be cached far longer than the prices it was built from. This
# stops leagues with no fixtures re-fetching live odds purely to learn "no fixtures
# today" on every run (measured: 7 network pulls / ~13s wasted per run).
FIXTURES_MAX_AGE_SECONDS = 6 * 3600

# Refuse to spend the last of the monthly allowance on a routine pull, so an
# unattended daily job can't exhaust the quota and leave the month blind.
QUOTA_FLOOR = 40

# FIXTURE CAPTURE may spend below QUOTA_FLOOR (the Architect authorized it:
# a single odds call buys a 6h-cached fixture LIST, which is the only source
# for EFL/UCL-qualifier fixtures). But it may never spend the last of the
# month — the framework must keep working, not exhaust itself. So fixture
# capture stops at this HARD floor instead.
QUOTA_HARD_FLOOR = 5

# Verified live against /v4/sports on 2026-08-10 — every key below returned
# active=True. Listing sports is free; only odds calls cost credits.
SPORT_KEYS = {
    # one unified pool (ID402 softness tiers removed 2026-08-10) — every
    # whitelisted league is deploy-eligible, no cap
    "Eredivisie": "soccer_netherlands_eredivisie",
    "Danish Superliga": "soccer_denmark_superliga",
    "Belgian Pro League": "soccer_belgium_first_div",
    "Scottish Premiership": "soccer_spl",
    "Ekstraklasa": "soccer_poland_ekstraklasa",
    "Championship": "soccer_efl_champ",
    "Serie A": "soccer_italy_serie_a",
    "Bundesliga": "soccer_germany_bundesliga",
    "Ligue 1": "soccer_france_ligue_one",
    "Primeira Liga": "soccer_portugal_primeira_liga",
    "Premier League": "soccer_epl",
    "La Liga": "soccer_spain_la_liga",
    # Austrian Bundesliga — verified live 2026-08-07 against the Odds API
    # /v4/sports list ("soccer_austria_bundesliga", active). No thesportsdb ID
    # exists on the free key and no history source covers it, so the ODDS feed
    # is its active fixture-capture path (same as Champions League), and the
    # fixtures it returns are honestly unrated NO DATA until a history source
    # exists.
    "Austrian Bundesliga": "soccer_austria_bundesliga",
    # Champions League qualifying is the only current-season continental
    # fixtures source in this framework: TheSportsDB's UCL feed lags weeks
    # behind and API-Football's free tier stops at 2024. Verified live
    # 2026-08-05 — returns the qualification fixtures with real book prices.
    "Champions League": "soccer_uefa_champs_league_qualification",
    # Cup competitions verified live 2026-08-06 (ratified). EFL Cup and
    # J-League carry real prices on the free tier; Europa/Conference quals do
    # NOT (no active sport key) — those stay TSDB-only and unpriced, which the
    # cup-training logger handles by logging O1.5 outcome evidence without
    # fabricating a price (HR35). EFL Cup is on the whitelist (one unified pool
    # — Architect 2026-08-10), so its fixtures appear on the daily board.
    "EFL Cup": "soccer_england_efl_cup",
    "J League": "soccer_japan_j_league",
    # HNL (Croatian First League) — UNVERIFIED PROBE, added 2026-08-10.
    # The key "soccer_croatia_hnl" is the standard Odds API name for the HNL but
    # could not be confirmed active at add time (no ODDS_API_KEY in the build
    # env). HR35: nothing claimed verified without the probe — the next run with
    # a key must check /v4/sports before trusting this entry (see Phase 3 notes
    # in docs/LEAGUE_DATA_COVERAGE.md). football-data.co.uk does not cover
    # Croatia (no T1 history), so the odds feed is the intended fixture-capture
    # path. Fixtures returned are honestly unrated NO DATA until a history source
    # exists (API-Football paid plan is the documented path).
    "HNL": "soccer_croatia_hnl",
}

# A THIRD naming convention to reconcile (football-data.co.uk and TheSportsDB
# being the other two). Same rule as the others: explicit pairs only, verified
# against both sides. Never fuzzy-matched — a silent mis-map would attach a
# real price to the wrong club, which is worse than an honest gap.
TEAM_ALIASES: dict[str, dict[str, str]] = {
    "Scottish Premiership": {
        "Dundee FC": "Dundee",
        "Falkirk F.C.": "Falkirk",
        "Heart of Midlothian": "Hearts",
    },
    # The odds feed favours official/registered club names (FC, SC, KV, IF
    # prefixes and suffixes) where football-data.co.uk uses the short form.
    # Every pair below was verified by diffing the two sources' live team
    # lists; clubs genuinely new to the division are deliberately absent.
    "Eredivisie": {
        "FC Twente Enschede": "Twente",
        "FC Utrecht": "Utrecht",
        "FC Zwolle": "Zwolle",
        "Fortuna Sittard": "For Sittard",
        "NEC Nijmegen": "Nijmegen",
        "SC Telstar": "Telstar",
        # Newly promoted, so the model has no rating for it — but the name is
        # still normalised, so the "new to this division" check recognises it
        # instead of reporting it as an unexplained mismatch.
        "SC Cambuur": "Cambuur",
    },
    "Danish Superliga": {
        "Brondby IF": "Brondby",
        "OB Odense BK": "Odense",
        "Silkeborg IF": "Silkeborg",
        "SonderjyskE": "Sonderjyske",
        "Viborg FF": "Viborg",
    },
    "Belgian Pro League": {
        "Cercle Brugge KSV": "Cercle Brugge",
        "KV Kortrijk": "Kortrijk",
        "KV Mechelen": "Mechelen",
        "Leuven": "Oud-Heverlee Leuven",
        "RAAL La Louvi\xe8re": "RAAL La Louviere",
        "Royal Antwerp": "Antwerp",
        "SV Zulte-Waregem": "Waregem",
        "Sint Truiden": "St Truiden",
        "Standard Liege": "Standard",
        "Union Saint-Gilloise": "St. Gilloise",
        # Promoted for 2026/27 — unrated, but normalised (see Cambuur note).
        "Lommel SK": "Lommel",
        "SK Beveren": "Beveren",
    },
    # Polish clubs: the Odds API carries full names with diacritics,
    # football-data.co.uk carries shortened ASCII. Every pair verified against
    # both sources' actual team lists.
    "Ekstraklasa": {
        "G\xf3rnik Zabrze": "Gornik Zabrze",
        "Jagiellonia Białystok": "Jagiellonia",
        "Lech Poznań": "Lech Poznan",
        "Legia Warszawa": "Legia",
        "Pogoń Szczecin": "Pogon Szczecin",
        "Rak\xf3w Częstochowa": "Rakow",
        "Widzew Ł\xf3dź": "Widzew Lodz",
        "Wisła Płock": "Wisla Plock",
        "Zagłębie Lubin": "Zaglebie",
    },
    # Champions League qualifiers come from the odds feed; the club names there
    # are the registered/official forms. The cross-league model stores the
    # api-football spellings. Each pair verified against the fitted pool's own
    # team keys (engine/cross_league fit, 2026-08-05).
    "Champions League": {
        "AGF Aarhus": "Aarhus",
        "Fenerbahce": "Fenerbahçe",
        "SK Sturm Graz": "Sturm Graz",
    },
}


@dataclass
class MarketQuote:
    """One side of one market at one moment, with its provenance (ID400)."""
    price: Optional[float] = None
    bookmaker: Optional[str] = None
    n_books: int = 0
    captured_at: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.price is not None


@dataclass
class FixtureOdds:
    league: str
    home_team: str          # already mapped to model keys
    away_team: str
    kickoff_utc: str
    home: MarketQuote = field(default_factory=MarketQuote)
    draw: MarketQuote = field(default_factory=MarketQuote)
    away: MarketQuote = field(default_factory=MarketQuote)
    over25: MarketQuote = field(default_factory=MarketQuote)
    under25: MarketQuote = field(default_factory=MarketQuote)
    source: str = "the-odds-api.com"
    source_tier: str = "T1"
    notes: list[str] = field(default_factory=list)


class QuotaExhausted(SourceNoData):
    """Raised rather than silently returning an empty board.

    A deliberate monthly guard (500 free credits / reset), NOT a transient
    outage — so it must not trip a circuit breaker. Subclassing SourceNoData
    makes the multi-source fall through to the next provider without recording
    a failure; run_daily still catches it by class for the honest board flag."""


def _get_key() -> str:
    """The PRIMARY Odds API key — the Architect's personal key."""
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "ODDS_API_KEY not set. Free key at https://the-odds-api.com/ — "
            "put it in .env (gitignored) or as a GitHub Actions secret.")
    return key


def _odds_keys() -> list[str]:
    """Candidate keys in priority order.

    Architect model (2026-08-11): the personal API key is the MAIN source and
    the free-tier monthly reset is the BACKUP. The pipeline walks ODDS_API_KEY
    first, then the optional ODDS_API_KEY_BACKUP (paste a second key there for
    a true main/backup pair — a fresh free-tier key works and resets monthly;
    each key pays its own 500/month)."""
    keys = [k for k in (os.environ.get("ODDS_API_KEY"),
                        os.environ.get("ODDS_API_KEY_BACKUP")) if k]
    if not keys:
        raise RuntimeError(
            "ODDS_API_KEY not set. Free key at https://the-odds-api.com/ — "
            "put it in .env (gitignored) or as a GitHub Actions secret.")
    return keys


def _probe_key(key: str) -> tuple[int, int]:
    """(used, remaining) for ONE key. Listing sports costs nothing, so the
    probe is free."""
    r = get_protected(f"{API_BASE}/sports", breaker_name="the_odds_api",
                      params={"apiKey": key}, timeout=25)
    return (int(r.headers.get("x-requests-used", -1)),
            int(r.headers.get("x-requests-remaining", -1)))


_active_key: Optional[str] = None  # last key found above the floor (process cache)


def _resolve_key(floor: int) -> tuple[str, int, int]:
    """(key, used, remaining) for the first key with remaining >= floor.

    Walks ODDS_API_KEY then ODDS_API_KEY_BACKUP and remembers the winner for
    the process so a league-by-league pull doesn't re-probe on every call.
    Raises QuotaExhausted when NO key is above the floor, reporting the best
    remaining honestly (HR35 — never pretends a spent key has quota)."""
    global _active_key
    if _active_key is not None:
        used, remaining = _probe_key(_active_key)
        if remaining >= floor:
            return _active_key, used, remaining
        _active_key = None  # spent since we last checked — re-walk the list
    best_used, best_rem, best_key = -1, -1, ""
    for key in _odds_keys():
        used, remaining = _probe_key(key)
        if remaining >= floor:
            _active_key = key
            return key, used, remaining
        if remaining > best_rem:
            best_used, best_rem, best_key = used, remaining, key
    raise QuotaExhausted(
        f"Odds API quota spent across all keys (best remaining {best_rem} on "
        f"{best_key or 'no key'}, floor {floor}). Refusing to spend the month "
        f"— entry prices are NO DATA — PENDING. The free tier resets monthly; "
        f"set a fresh key in ODDS_API_KEY / ODDS_API_KEY_BACKUP or wait for "
        f"the reset.")


def map_team(league: str, name: str) -> str:
    """Odds API name -> model key. Unknown names pass through UNCHANGED so the
    caller reports NO DATA — PENDING instead of guessing a match."""
    return TEAM_ALIASES.get(league, {}).get(name, name)


def check_quota() -> tuple[int, int]:
    """(used, remaining) on the PRIMARY key. Listing sports costs nothing, so
    this is a free probe (kept on the primary for external callers like the
    health monitor / league audit)."""
    if requests is None:
        raise RuntimeError("requests not installed")
    return _probe_key(_get_key())


# Books the Architect can actually bet into, in preference order. Taking the
# best price ACROSS ALL books quotes a number that may sit at an operator he
# has no account with — which inflates every MES and every CLV figure derived
# from it. A price you cannot take is not a price. (Pattern taken from
# DataEngine v1.0, which had this right.)
BOOKMAKER_PRIORITY = ("bet365", "pinnacle", "betfair_ex_uk", "williamhill",
                      "betfair_ex_eu")


def _best_price(event: dict, market_key: str, outcome_name: str,
                 point: Optional[float] = None,
                 priority: tuple[str, ...] = BOOKMAKER_PRIORITY) -> MarketQuote:
    """Price for one outcome, preferring a book the Architect can reach.

    Walks `priority` in order and returns the first book that quotes this
    outcome. Only if NONE of them do does it fall back to the best price
    across all books — and that fallback is marked, because it is a price he
    may not be able to get. n_books is always the full count, so a single
    outlier quote stays visibly distinguishable from a consensus one."""
    quotes: dict[str, float] = {}
    for bm in event.get("bookmakers", []):
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            for o in m.get("outcomes", []):
                if o.get("name") != outcome_name:
                    continue
                if point is not None and o.get("point") != point:
                    continue
                if o.get("price") is not None:
                    quotes[bm.get("key")] = o["price"]

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not quotes:
        return MarketQuote(captured_at=now)

    for book in priority:
        if book in quotes:
            return MarketQuote(price=quotes[book], bookmaker=book,
                                n_books=len(quotes), captured_at=now)

    # No reachable book quoted it — best available, flagged by the book name.
    book = max(quotes, key=quotes.get)
    return MarketQuote(price=quotes[book], bookmaker=f"{book} (not a priority book)",
                        n_books=len(quotes), captured_at=now)


def _cache_path(league: str) -> Path:
    return CACHE_DIR / f"{league.replace(' ', '_')}.json"


def _read_cache(league: str) -> Optional[list[dict]]:
    p = _cache_path(league)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    age = time.time() - blob.get("fetched_at", 0)
    if age > ODDS_MAX_AGE_SECONDS:
        return None  # V2 recency: stale odds are REJECTED, not served
    return blob.get("events")


def _write_cache(league: str, events: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(league).write_text(
        json.dumps({"fetched_at": time.time(), "events": events}), encoding="utf-8")


def fetch_odds(league: str, regions: str = "uk", markets: str = "h2h,totals",
                use_cache: bool = True,
                fixture_capture: bool = False) -> tuple[list[FixtureOdds], list[str]]:
    """Live prices for one league. Returns (fixtures, flags).

    Cost is len(regions) * len(markets) credits — the defaults are 1 x 2 = 2.
    Raises QuotaExhausted rather than quietly returning nothing.

    `fixture_capture=True` relaxes the quota floor from QUOTA_FLOOR down to
    QUOTA_HARD_FLOOR (Architect-authorized): a fixture LIST is cached 6h, so
    one spend buys far more coverage than a routine price pull. The price-pull
    floor (40) is untouched for every other caller."""
    flags: list[str] = []
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch odds")
    if league not in SPORT_KEYS:
        raise SourceNoData(f"'{league}' has no verified Odds API sport key.")

    events = _read_cache(league) if use_cache else None
    if events is None:
        floor = QUOTA_HARD_FLOOR if fixture_capture else QUOTA_FLOOR
        try:
            key, used, remaining = _resolve_key(floor)
        except QuotaExhausted as qe:
            # The Odds API monthly quota is spent on every key. Before
            # degrading to NO DATA, try the free API-Football fallback (same
            # bookmakers, 1X2 + totals, 100 requests/day). Only for a routine
            # PRICE pull — fixture capture stays on the cache discipline that
            # is its whole purpose. The import is lazy to avoid a circular
            # import (api_football_odds imports our MarketQuote/FixtureOdds
            # contract).
            if not fixture_capture:
                try:
                    from data import api_football_odds as _af_fallback
                    fixtures, afl = _af_fallback.fetch_odds(league)
                    return fixtures, [f"{league}: Odds API quota spent across "
                                      f"all keys — served via api-football "
                                      f"free fallback"] + afl
                except QuotaExhausted:
                    raise
                except Exception as e:
                    raise QuotaExhausted(
                        f"Odds API quota spent across all keys; api-football "
                        f"fallback failed ({e}). Refusing to spend the month — "
                        f"entry prices are NO DATA — PENDING.") from e
            raise qe
        r = get_protected(f"{API_BASE}/sports/{SPORT_KEYS[league]}/odds",
                          breaker_name="the_odds_api",
                          params={"apiKey": key, "regions": regions,
                                  "markets": markets, "oddsFormat": "decimal"},
                          timeout=30)
        events = r.json()
        _write_cache(league, events)
        flags.append(f"{league}: odds pulled live "
                     f"({r.headers.get('x-requests-remaining')} API credits left)")
    else:
        flags.append(f"{league}: odds served from cache (under the 60-minute "
                     f"V2 recency cap)")

    out: list[FixtureOdds] = []
    for e in events:
        home_raw, away_raw = e.get("home_team"), e.get("away_team")
        if not home_raw or not away_raw:
            continue  # HR35 — incomplete record, skipped not guessed
        fx = FixtureOdds(
            league=league,
            home_team=map_team(league, home_raw),
            away_team=map_team(league, away_raw),
            kickoff_utc=e.get("commence_time", ""),
            home=_best_price(e, "h2h", home_raw),
            draw=_best_price(e, "h2h", "Draw"),
            away=_best_price(e, "h2h", away_raw),
            over25=_best_price(e, "totals", "Over", 2.5),
            under25=_best_price(e, "totals", "Under", 2.5),
        )
        if not fx.over25.available:
            fx.notes.append("Over/Under 2.5 not quoted — NO DATA — PENDING")
        out.append(fx)
    return out, flags


def _fixtures_cache_path(league: str, days_ahead: int) -> Path:
    return FIXTURES_DIR / f"{league.replace(' ', '_')}_{days_ahead}d.json"


def _read_fixtures_cache(league: str, days_ahead: int
                         ) -> Optional[tuple[list, dict, list]]:
    p = _fixtures_cache_path(league, days_ahead)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - blob.get("fetched_at", 0) > FIXTURES_MAX_AGE_SECONDS:
        return None
    # Pairs round-trip as JSON lists, but callers use them as (home, away)
    # TUPLES (dict keys, matches); restore the type. Dates were stored under
    # "||"-joined keys (a tuple isn't JSON-serialisable).
    pairs = [tuple(p) for p in blob.get("pairs", [])]
    dates = {tuple(k.split("||")): v for k, v in blob.get("dates", {}).items()}
    return pairs, dates, blob.get("flags", [])


def _write_fixtures_cache(league: str, days_ahead: int,
                          pairs: list, dates: dict, flags: list) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    _fixtures_cache_path(league, days_ahead).write_text(json.dumps({
        "fetched_at": time.time(), "pairs": pairs,
        "dates": {"||".join(k): v for k, v in dates.items()}, "flags": flags,
    }), encoding="utf-8")


def fixtures_from_odds(league: str, days_ahead: int = 14
                        ) -> tuple[list[tuple[str, str]], dict[tuple[str, str], str], list[str]]:
    """Derive the upcoming fixture LIST from the odds feed.

    A priced event is by definition an upcoming fixture, so where a dedicated
    fixtures source has no verified league ID this recovers the league rather
    than dropping it. That is what unblocks Ekstraklasa — a whitelisted
    (unified-pool, deploy-eligible) league with 306 matches of history and live
    prices, which was otherwise scanning as NO DATA purely for want of a fixture
    list.

    Returns (pairs, dates_by_pair, flags). Deduplicated: the feed can return
    the same fixture more than once, and a duplicate would be logged as two
    separate paper legs on one match.

    The DERIVED LIST is cached per (league, days_ahead) for 6 hours — a
    schedule is stable, unlike a price — so a warm run costs no odds API quota
    (the live prices were only needed once, to build the list)."""
    cached = _read_fixtures_cache(league, days_ahead)
    if cached is not None:
        return cached

    from datetime import date as _date, timedelta as _td
    flags: list[str] = []
    # Fixture capture may spend below the price-pull floor (Architect-
    # authorized): one spend buys a 6h-cached list, the only source for
    # EFL/UCL-qualifier fixtures. Stops at QUOTA_HARD_FLOOR regardless.
    quotes, oflags = fetch_odds(league, fixture_capture=True)
    flags += oflags

    horizon = _date.today() + _td(days=days_ahead)
    pairs: list[tuple[str, str]] = []
    dates: dict[tuple[str, str], str] = {}
    for q in quotes:
        day = (q.kickoff_utc or "")[:10]
        if not day:
            continue  # HR35 — no date means it could never be settled correctly
        try:
            if _date.fromisoformat(day) > horizon:
                continue
        except ValueError:
            continue
        key = (q.home_team, q.away_team)
        if key in dates:
            continue  # already seen — never log one match twice
        dates[key] = day
        pairs.append(key)

    flags.append(f"{league}: {len(pairs)} fixture(s) derived from the odds feed "
                 f"(no dedicated fixtures source for this league)")
    _write_fixtures_cache(league, days_ahead, pairs, dates, flags)
    return pairs, dates, flags


def index_by_fixture(fixtures: list[FixtureOdds]) -> dict[tuple[str, str], FixtureOdds]:
    """Lookup by (home, away) using MODEL keys, so the board can join odds onto
    its own fixtures without another round of name matching."""
    return {(f.home_team, f.away_team): f for f in fixtures}
