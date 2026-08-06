"""CL-LIVE closing-line capture — close a paper leg's CLV before the archive.

HR46 defines three capture paths for a closing line: CL-LIVE (session running),
CL-ARCHIVE (odds archive) and CL-PM (Polymarket, shelved). Until now only
CL-ARCHIVE could actually CLOSE a leg, and it arrives on football-data's
schedule (next morning) and only for the markets football-data publishes
(e.g. Danish Superliga carries 1X2 closing prices but NO totals). The result:
a paper leg could not earn a CLV number until the archive published — a
structural gap, not a calibration truth.

This module closes that gap. It records the live feed's price near kickoff as
the closing line (CL-LIVE), so a leg can settle the moment its match kicks off
and covers markets the archive never serves.

HONESTY RULE (the whole point):
  A price captured hours before kickoff is NOT a closing line — it is an
  intraday price and treating it as the close would manufacture CLV out of
  nothing. So a leg is only captured when its kickoff is inside the window:
  no earlier than CLOSING_WINDOW_MINUTES before kickoff, no later than
  KICKOFF_GRACE_MINUTES after it (once play is underway the pre-match price is
  gone anyway — the Odds API stops quoting h2h, so the quote simply won't be
  available). A leg outside that window is left PENDING, not estimated (HR35).

  First capture wins: an existing closing line is never overwritten here. When
  the archive later publishes, grade_open_legs UPGRADES a CL-LIVE close to the
  canonical CL-ARCHIVE price — see run_daily.grade_open_legs.
"""
from __future__ import annotations

import argparse
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


def capture_closing_lines(log: CLVLog, leagues: list[str],
                          odds_index: Optional[dict] = None,
                          now: Optional[datetime] = None,
                          phase: str = PAPER_PHASE) -> tuple[int, list[str]]:
    """Capture a CL-LIVE closing line for pending legs whose kickoff is inside
    the window. Returns (captured, flags).

    `odds_index` maps (home, away) -> FixtureOdds. When provided it is used
    as-is (the daily run passes the index it already fetched, so capture costs
    zero extra quota); otherwise each league's odds are fetched (cached).
    `phase` filters which legs are eligible — the daily run uses the default
    PAPER_PHASE; the cup-training loop passes its own phase so those legs get
    closing lines too.
    """
    now = now or datetime.now(timezone.utc)
    flags: list[str] = []
    pending = [l for l in log.legs
               if l.phase == phase and l.hit is None
               and l.closing_odds is None and l.entry_odds is not None
               and l.match_date]
    if not pending:
        return 0, flags

    # Group the pending legs by league so we fetch once per league, not per leg.
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
            except Exception as e:  # QuotaExhausted, network, etc.
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
            # HR48-style date guard: never close a leg against a same-pairing
            # meeting from another day.
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
        description="Capture CL-LIVE closing lines for pending paper legs "
                    "whose kickoff is within the closing window.")
    ap.add_argument("leagues", nargs="*",
                    help="leagues to scan (default: all softness A/B leagues)")
    a = ap.parse_args()
    from engine.softness import DEPLOY_ELIGIBLE_TIERS, SOFTNESS_TIER
    target = a.leagues or [lg for lg, t in SOFTNESS_TIER.items()
                           if t in DEPLOY_ELIGIBLE_TIERS]
    n, flags = capture_closing_lines(CLVLog(), target)
    for f in flags:
        print(f"  {f}")
    print(f"CL-LIVE closing lines captured: {n}")
