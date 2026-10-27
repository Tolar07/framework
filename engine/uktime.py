"""
UK TIME (Architect 2026-10-15: "we are in the UK, not Lagos ... by October
ending ... 1 hour difference" -> "UK time for everything").

Every time the Architect reads — kickoff times on the boards, when the board
and the morning check go out — follows the UK clock, daylight saving
included: BST (UTC+1) until the last Sunday of October, GMT (UTC+0) after it.
The board goes out at 21:47 UK and the morning check at 06:47 UK all year.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
SLOT_UK = {"evening": (21, 47), "morning": (6, 47)}       # UK wall-clock time
# Before the slot's UK time on its own day, inside these UK hours, a backup
# starter (GitHub cron, watchdog) is EARLY and must leave the slot to the clock.
EARLY_FROM = {"evening": 12, "morning": 3}


def uk(dt: datetime) -> datetime:
    return dt.astimezone(UK)


def hm(dt: datetime) -> str:
    """HH:MM on the UK clock."""
    return uk(dt).strftime("%H:%M")


def zone_name(dt: datetime) -> str:
    """'BST' or 'GMT' — which UK clock is in force at `dt`."""
    return uk(dt).tzname() or "UK"


def slot_start(slot: str, uk_day: date) -> datetime:
    """The UTC moment of `slot` on UK date `uk_day` (DST-aware)."""
    h, m = SLOT_UK[slot]
    return datetime(uk_day.year, uk_day.month, uk_day.day, h, m, tzinfo=UK).astimezone(ZoneInfo("UTC"))


def target_card(slot: str, uk_day: date) -> date:
    """The card a slot builds: the evening board is TOMORROW's, the morning check today's."""
    return uk_day + timedelta(days=1) if slot == "evening" else uk_day


def early(slot: str, now: datetime) -> bool:
    """True when it is the run-up to today's slot on the UK clock and the slot
    time has not come yet (e.g. a GitHub cron firing at 20:47 UTC = 20:47 GMT
    in winter, an hour before the 21:47 UK board)."""
    t = uk(now)
    h, m = SLOT_UK[slot]
    return EARLY_FROM[slot] <= t.hour and (t.hour, t.minute) < (h, m)
