"""
Fixture date validation gate for OLP XDV pipeline.
Ensures fixtures match the target date before processing.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Tuple

logger = logging.getLogger("fixture_date_gate")

# Tolerance for kickoff time matching (±12 hours = half a day)
# This allows fixtures that cross midnight UTC but are still "today" locally
KICKOFF_TOLERANCE = timedelta(hours=12)


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

    The check allows fixtures within ±12 hours of the target date to accommodate
    kickoff times that cross midnight UTC but are still considered "today's" fixtures.
    Fixtures from completely different matchdays (delta_days ≠ 0) are still rejected.
    """
    kept, rejected = [], []

    for f in fixtures:
        fixture_date = f.kickoff_utc.date()
        delta_days = (fixture_date - target_date).days

        # Allow fixtures within ±12 hours tolerance (half a day)
        # This handles cases where kickoff crosses midnight UTC but is still "today"
        if abs(delta_days) < 1 or (abs(delta_days) == 1 and abs((f.kickoff_utc - datetime.combine(target_date, datetime.min.time())).total_seconds()) <= KICKOFF_TOLERANCE.total_seconds()):
            kept.append(f)
            continue

        # Still reject if completely different day (more than 1 day difference)
        reason = (
            f"REJECTED {f.home} v {f.away} ({f.league}) — kickoff is "
            f"{fixture_date.isoformat()} ({delta_days:+d} days from target "
            f"{target_date.isoformat()}). This is a different matchday, not today's."
        )
        logger.warning(reason)
        rejected.append(reason)
        continue

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