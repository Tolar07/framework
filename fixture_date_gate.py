"""
Fixture date validation gate for OLP XDV pipeline.
Ensures fixtures match the target date before processing.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Tuple

logger = logging.getLogger("fixture_date_gate")


@dataclass
class DatedFixture:
    fixture_id: str
    home: str
    away: str
    league: str
    kickoff_utc: datetime   # the fixture's OWN kickoff, from the source feed
                             # — never the query date, never "now"


def validate_fixture_dates(
    fixtures: List[DatedFixture],
    target_date: date,
) -> Tuple[List[DatedFixture], List[str]]:
    """
    Returns (fixtures_actually_on_target_date, rejection_reasons).

    The check is deliberately simple and deliberately strict: does this
    fixture's own kickoff timestamp fall on the target date? If the
    source feed says 5 September and the board is for 2 September, the
    fixture is REJECTED — no tolerance window, no "close enough."

    A tolerance window is what lets a 3-day-ahead matchday leak in.
    """
    kept, rejected = [], []

    for f in fixtures:
        fixture_date = f.kickoff_utc.date()
        if fixture_date != target_date:
            delta_days = (fixture_date - target_date).days
            reason = (
                f"REJECTED {f.home} v {f.away} ({f.league}) — kickoff is "
                f"{fixture_date.isoformat()} ({delta_days:+d} days from target "
                f"{target_date.isoformat()}). This is a different matchday, not today's."
            )
            logger.warning(reason)
            rejected.append(reason)
            continue
        kept.append(f)

    if fixtures and not kept:
        logger.warning(
            "ALL %d fixture(s) rejected as wrong-date for %s. This usually means the "
            "fetch queried a forward window (next matchday / next N days) instead of "
            "the target date — check the date parameter passed to the fixtures API, "
            "not the API itself. An empty board is the correct output here; shipping "
            "another matchday's fixtures as today's is not.",
            len(fixtures), target_date.isoformat(),
        )

    return kept, rejected


def check_kickoff_time_diversity(fixtures: List[DatedFixture]) -> str | None:
    """
    Catches the 'one real kickoff time copied across every fixture' bug.

    Real matchdays stagger kickoffs. Five fixtures all showing the exact
    same minute is far more likely to be a placeholder/default than a
    genuine schedule — on the 2 Sep board, four of the five 18:30 times
    were wrong (the real times were 15:30 CEST).

    Returns a warning string if suspicious, else None. This is a FLAG,
    not a hard reject: genuine simultaneous kickoffs do exist (final
    matchday of a season, for instance), so a human/agent should see the
    flag rather than have the board silently emptied.
    """
    if len(fixtures) < 3:
        return None

    times = Counter(f.kickoff_utc.strftime("%H:%M") for f in fixtures)
    most_common_time, count = times.most_common(1)[0]

    if count == len(fixtures):
        return (
            f"SUSPICIOUS: all {len(fixtures)} fixtures show the identical kickoff time "
            f"{most_common_time}. Real matchdays normally stagger kickoffs. This is the "
            f"signature of one real time being copied across every row (as happened on "
            f"the 2 Sep board). Verify against the source feed before trusting these times."
        )
    return None


def run_full_date_check(
    fixtures: List[DatedFixture],
    target_date: date,
) -> Tuple[List[DatedFixture], List[str]]:
    """Convenience wrapper: date gate + kickoff-diversity flag together."""
    kept, rejected = validate_fixture_dates(fixtures, target_date)
    flag = check_kickoff_time_diversity(kept)
    if flag:
        logger.warning(flag)
        rejected.append(flag)
    return kept, rejected