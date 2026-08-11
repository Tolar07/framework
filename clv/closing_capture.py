"""CL-LIVE / CL-PM closing-line capture — close a paper leg's CLV before the archive.

HR46 defines three capture paths for a closing line: CL-LIVE (session running),
CL-ARCHIVE (odds archive) and CL-PM (Polymarket). CL-ARCHIVE arrives on
football-data's schedule (next morning) and only for the markets football-data
publishes (e.g. Danish Superliga carries 1X2 closing prices but NO totals). The
result: a paper leg could not earn a CLV number until the archive published — a
structural gap, not a calibration truth.

This module closes that gap with TWO live capture paths:
  - CL-LIVE: the live feed's price near kickoff (The Odds API / API-Football)
  - CL-PM: Polymarket's prediction-market price near kickoff (shelved until
    a Polymarket API key is provisioned; the plumbing is here so the gate
    doesn't wait on infrastructure)

A leg can settle the moment its match kicks off and covers markets the archive
never serves.

HONESTY RULE (the whole point):
  A price captured hours before kickoff is NOT a closing line — it is an
  intraday price and treating it as the close would manufacture CLV out of
  nothing. So a leg is only captured when its kickoff is inside the window:
  no earlier than CLOSING_WINDOW_MINUTES before kickoff, no later than
  KICKOFF_GRACE_MINUTES after it (once play is underway the pre-match price is
  gone anyway — the Odds API stops quoting h2h, so the quote simply won't be
  available). A leg outside that window is left PENDING, not estimated (HR35).

  First capture wins: an existing closing line is never overwritten here. When
  the archive later publishes, grade_open_legs UPGRADES a CL-LIVE/CL-PM close
  to the canonical CL-ARCHIVE price — see run_daily.grade_open_legs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PAPER_PHASE  # noqa: E402
from clv.clv_logger import CLVLog  # noqa: E402
from engine import markets as mkt  # noqa: E402
import pipeline.odds as odds  # noqa: E402

CLOSING_WINDOW_MINUTES = 60     # capture when kickoff is within the next hour
KICKOFF_GRACE_MINUTES = 10      # or within ten minutes after kickoff started
CLOSING_CAPTURE_PATH = "CL-LIVE"

# Polymarket constants (CL-PM path) — plumbing is here; live when a key exists
POLYMARKET_BASE = "https://gamma-api.polymarket.com"
POLYMARKET_TIMEOUT = 15
POLYMARKET_CLOSING_CAPTURE_PATH = "CL-PM"


def _minutes_to_kickoff(kickoff_utc: str, now: datetime) -> Optional[float]:
    """Minutes from now to the kickoff (positive = not yet started). None when
    the kickoff string cannot be parsed — that fixture cannot be captured."""
    try:
        ko = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if ko.tzinfo is None:
        ko = ko.replace(tzinfo=timezone.utc)
    return (ko - now).total_seconds() / 60.0


def _in_window(minutes_to_kickoff: Optional[float]) -> bool:
    """True only when the price we could capture IS the closing line: kickoff
    imminent (within the window, positive) or just started (within the grace
    period, negative)."""
    if minutes_to_kickoff is None:
        return False
    return (-KICKOFF_GRACE_MINUTES <= minutes_to_kickoff
            <= CLOSING_WINDOW_MINUTES)


def _polymarket_key() -> Optional[str]:
    """Return the Polymarket API key if set, else None.

    No exception — a missing key just means CL-PM is not live (shelved
    infrastructure, not a fault)."""
    return os.environ.get("POLYMARKET_API_KEY")


def _polymarket_headers() -> dict:
    key = _polymarket_key()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _polymarket_market_key(league: str, home: str, away: str,
                           market: str) -> str:
    """Construct the Polymarket market identifier for a fixture/market.

    Polymarket uses a specific format; we construct a deterministic key that
    matches their convention. The actual mapping will need calibration when
    the key is provisioned — this is the plumbing skeleton."""
    # Normalize to a compact form Polymarket would recognize
    league_clean = league.lower().replace(" ", "_")
    home_clean = home.lower().replace(" ", "_")
    away_clean = away.lower().replace(" ", "_")
    market_map = {
        mkt.HOME: "home_win",
        mkt.DRAW: "draw",
        mkt.AWAY: "away_win",
        mkt.OVER_25: "over_2_5",
        mkt.UNDER_25: "under_2_5",
    }
    mkey = market_map.get(market, market.lower())
    return f"{league_clean}_{home_clean}_{away_clean}_{mkey}"


def _fetch_polymarket_price(league: str, home: str, away: str,
                            market: str) -> Optional[float]:
    """Fetch the current Polymarket price for a specific market.

    Returns the decimal odds (price) if available, else None.
    HR35: a missing price is None → NO DATA — PENDING, never guessed."""
    key = _polymarket_key()
    if not key:
        return None
    try:
        import requests
    except ImportError:
        return None

    mkey = _polymarket_market_key(league, home, away, market)
    url = f"{POLYMARKET_BASE}/markets/{mkey}"
    try:
        r = requests.get(url, headers=_polymarket_headers(), timeout=POLYMARKET_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        # Polymarket returns probability; convert to decimal odds = 1/prob
        prob = data.get("probability") or data.get("last_trade_price")
        if prob is not None:
            try:
                p = float(prob)
                if 0 < p < 1:
                    return round(1.0 / p, 2)
            except (TypeError, ValueError):
                pass
        return None
    except Exception:
        return None


def _capture_polymarket_closing_lines(log: CLVLog, leagues: list[str],
                                       odds_index: Optional[dict] = None,
                                       now: Optional[datetime] = None,
                                       phase: str = PAPER_PHASE) -> tuple[int, list[str]]:
    """Capture a CL-PM closing line from Polymarket for pending legs.

    Returns (captured, flags). Only runs when POLYMARKET_API_KEY is set.
    """
    if not _polymarket_key():
        return 0, []

    now = now or datetime.now(timezone.utc)
    flags: list[str] = []
    pending = [l for l in log.legs
               if l.phase == phase and l.hit is None
               and l.closing_odds is None and l.entry_odds is not None
               and l.match_date]
    if not pending:
        return 0, flags

    by_league: dict[str, list] = {}
    for leg in pending:
        by_league.setdefault(leg.league, []).append(leg)

    captured = 0
    for league in leagues:
        legs = by_league.get(league)
        if not legs:
            continue
        for leg in legs:
            try:
                home, away = [s.strip() for s in leg.fixture.split(" v ", 1)]
            except ValueError:
                continue
            # HR48 date guard
            fx = (odds_index or {}).get((home, away))
            if fx is not None:
                kickoff_date = fx.kickoff_utc[:10]
                if kickoff_date != leg.match_date[:10]:
                    continue
            minutes = _minutes_to_kickoff(fx.kickoff_utc if fx else leg.match_date + "T00:00:00Z", now)
            if not _in_window(minutes):
                continue
            price = _fetch_polymarket_price(league, home, away, leg.market)
            if price is None:
                continue
            log.log_close(leg.leg_id, closing_odds=price,
                          closing_capture_path=POLYMARKET_CLOSING_CAPTURE_PATH)
            captured += 1
            flags.append(f"{leg.fixture} / {leg.market}: CL-PM closing line "
                         f"{price} (kickoff in {int(minutes)} min)")

    if captured:
        flags.append(f"CL-PM closing lines captured this run: {captured}")
    return captured, flags


def capture_closing_lines(log: CLVLog, leagues: list[str],
                          odds_index: Optional[dict] = None,
                          now: Optional[datetime] = None,
                          phase: str = PAPER_PHASE) -> tuple[int, list[str]]:
    """Capture closing lines via ALL available paths (CL-LIVE + CL-PM).

    Returns (total_captured, flags). CL-LIVE uses live bookmaker feeds;
    CL-PM uses Polymarket when key is provisioned. First capture wins.
    """
    now = now or datetime.now(timezone.utc)
    flags: list[str] = []

    # CL-LIVE: live bookmaker odds (existing logic)
    n_live, live_flags = _capture_live_closing_lines(log, leagues, odds_index, now, phase)
    flags += live_flags

    # CL-PM: Polymarket (new plumbing)
    n_pm, pm_flags = _capture_polymarket_closing_lines(log, leagues, odds_index, now, phase)
    flags += pm_flags

    total = n_live + n_pm
    if total:
        flags.append(f"Total closing lines captured (CL-LIVE + CL-PM): {total}")
    return total, flags


def _capture_live_closing_lines(log: CLVLog, leagues: list[str],
                                 odds_index: Optional[dict] = None,
                                 now: Optional[datetime] = None,
                                 phase: str = PAPER_PHASE) -> tuple[int, list[str]]:
    """CL-LIVE: capture closing line from live bookmaker feeds.

    This is the original capture_closing_lines logic, renamed for clarity."""
    now = now or datetime.now(timezone.utc)
    flags: list[str] = []
    pending = [l for l in log.legs
               if l.phase == phase and l.hit is None
               and l.closing_odds is None and l.entry_odds is not None
               and l.match_date]
    if not pending:
        return 0, flags

    by_league: dict[str, list] = {}
    for leg in pending:
        by_league.setdefault(leg.league, []).append(leg)

    captured = 0
    for league in leagues:
        legs = by_league.get(league)
        if not legs:
            continue
        index = odds_index
        if index is None:
            try:
                fixtures, oflags = odds.fetch_odds(league)
                index = odds.index_by_fixture(fixtures)
                flags += oflags
            except Exception as e:
                flags.append(f"{league}: CL-LIVE capture skipped ({e})")
                continue
        for leg in legs:
            try:
                home, away = [s.strip() for s in leg.fixture.split(" v ", 1)]
            except ValueError:
                continue
            fx = (index or {}).get((home, away))
            if fx is None:
                continue
            # HR48-style date guard
            kickoff_date = fx.kickoff_utc[:10]
            if kickoff_date != leg.match_date[:10]:
                continue
            minutes = _minutes_to_kickoff(fx.kickoff_utc, now)
            if not _in_window(minutes):
                continue
            q = mkt.quote(leg.market, fx)
            if q is None or not q.available:
                continue
            log.log_close(leg.leg_id, closing_odds=q.price,
                          closing_capture_path=CLOSING_CAPTURE_PATH)
            captured += 1
            flags.append(f"{leg.fixture} / {leg.market}: CL-LIVE closing line "
                         f"{q.price} (kickoff in {int(minutes)} min)")

    if captured:
        flags.append(f"CL-LIVE closing lines captured this run: {captured}")
    return captured, flags


if __name__ == "__main__":
    """Standalone capture pass — schedule this near kickoff to close legs the
    archive cannot. Example:
        python -m clv.closing_capture                  # all deploy leagues
        python -m clv.closing_capture Eredivisie       # one league
    """
    ap = argparse.ArgumentParser(
        description="Capture CL-LIVE + CL-PM closing lines for pending paper legs "
                    "whose kickoff is within the closing window.")
    ap.add_argument("leagues", nargs="*",
                    help="leagues to scan (default: all whitelisted leagues)")
    a = ap.parse_args()
    from engine.leagues import WHITELISTED_LEAGUES
    target = a.leagues or list(WHITELISTED_LEAGUES)
    n, flags = capture_closing_lines(CLVLog(), target)
    for f in flags:
        print(f"  {f}")
    print(f"Closing lines captured (CL-LIVE + CL-PM): {n}")
