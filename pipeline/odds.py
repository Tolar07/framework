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
  call therefore costs 4, and five deploy leagues once daily would burn
  ~600/month — over the cap. Defaults here are ONE region ('uk', where Bet365
  sits) and two markets, i.e. 2 credits per league per pull: about 300/month
  for the five deploy leagues. `check_quota()` refuses to spend when the
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

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://api.the-odds-api.com/v4"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "odds"

# ID403.1 V2: odds go stale at 60 minutes. A cached price older than this is
# REJECTED, not merely flagged.
ODDS_MAX_AGE_SECONDS = 60 * 60

# Refuse to spend the last of the monthly allowance on a routine pull, so an
# unattended daily job can't exhaust the quota and leave the month blind.
QUOTA_FLOOR = 40

# Verified live against /v4/sports on 2026-08-03 — every key below returned
# active=True. Listing sports is free; only odds calls cost credits.
SPORT_KEYS = {
    # deploy-eligible (softness A/B)
    "Eredivisie": "soccer_netherlands_eredivisie",
    "Danish Superliga": "soccer_denmark_superliga",
    "Belgian Pro League": "soccer_belgium_first_div",
    "Scottish Premiership": "soccer_spl",
    "Ekstraklasa": "soccer_poland_ekstraklasa",
    # scan-only (softness C/D) — never a capital pick, pulled only if asked
    "Championship": "soccer_efl_champ",
    "Serie A": "soccer_italy_serie_a",
    "Bundesliga": "soccer_germany_bundesliga",
    "Ligue 1": "soccer_france_ligue_one",
    "Primeira Liga": "soccer_portugal_primeira_liga",
    "Premier League": "soccer_epl",
    "La Liga": "soccer_spain_la_liga",
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


class QuotaExhausted(RuntimeError):
    """Raised rather than silently returning an empty board."""


def _get_key() -> str:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "ODDS_API_KEY not set. Free key at https://the-odds-api.com/ — "
            "put it in .env (gitignored) or as a GitHub Actions secret.")
    return key


def map_team(league: str, name: str) -> str:
    """Odds API name -> model key. Unknown names pass through UNCHANGED so the
    caller reports NO DATA — PENDING instead of guessing a match."""
    return TEAM_ALIASES.get(league, {}).get(name, name)


def check_quota() -> tuple[int, int]:
    """(used, remaining). Listing sports costs nothing, so this is a free probe."""
    if requests is None:
        raise RuntimeError("requests not installed")
    r = requests.get(f"{API_BASE}/sports", params={"apiKey": _get_key()}, timeout=25)
    r.raise_for_status()
    return (int(r.headers.get("x-requests-used", -1)),
            int(r.headers.get("x-requests-remaining", -1)))


def _best_price(event: dict, market_key: str, outcome_name: str,
                 point: Optional[float] = None) -> MarketQuote:
    """Best (longest) price across books for one outcome.

    Best-of rather than an average: an average is a price nobody offers, and
    the Architect bets at a real book. n_books is recorded so a price quoted by
    a single outlier book is visibly distinguishable from a consensus one."""
    best, book, n = None, None, 0
    for bm in event.get("bookmakers", []):
        for m in bm.get("markets", []):
            if m.get("key") != market_key:
                continue
            for o in m.get("outcomes", []):
                if o.get("name") != outcome_name:
                    continue
                if point is not None and o.get("point") != point:
                    continue
                n += 1
                price = o.get("price")
                if price is not None and (best is None or price > best):
                    best, book = price, bm.get("key")
    return MarketQuote(price=best, bookmaker=book, n_books=n,
                        captured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


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
                use_cache: bool = True) -> tuple[list[FixtureOdds], list[str]]:
    """Live prices for one league. Returns (fixtures, flags).

    Cost is len(regions) * len(markets) credits — the defaults are 1 x 2 = 2.
    Raises QuotaExhausted rather than quietly returning nothing."""
    flags: list[str] = []
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch odds")
    if league not in SPORT_KEYS:
        raise ValueError(f"'{league}' has no verified Odds API sport key.")

    events = _read_cache(league) if use_cache else None
    if events is None:
        used, remaining = check_quota()
        if remaining < QUOTA_FLOOR:
            raise QuotaExhausted(
                f"Odds API quota down to {remaining} (floor {QUOTA_FLOOR}). "
                f"Refusing to spend it on a routine pull — today's entry prices "
                f"are NO DATA — PENDING rather than exhausting the month.")
        r = requests.get(f"{API_BASE}/sports/{SPORT_KEYS[league]}/odds",
                          params={"apiKey": _get_key(), "regions": regions,
                                  "markets": markets, "oddsFormat": "decimal"},
                          timeout=30)
        r.raise_for_status()
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


def index_by_fixture(fixtures: list[FixtureOdds]) -> dict[tuple[str, str], FixtureOdds]:
    """Lookup by (home, away) using MODEL keys, so the board can join odds onto
    its own fixtures without another round of name matching."""
    return {(f.home_team, f.away_team): f for f in fixtures}
