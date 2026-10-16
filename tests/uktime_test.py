"""UK time (Architect 2026-10-15: "we are in the UK, not Lagos" -> "UK time for
everything"): the board slots and every time on the boards follow the UK
clock, daylight saving included — BST (UTC+1) until Sunday 25 Oct 2026, GMT
(UTC+0) after it."""
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import uktime  # noqa: E402


def test_slot_start_follows_daylight_saving():
    assert uktime.slot_start("evening", date(2026, 10, 24)) == datetime(2026, 10, 24, 20, 47, tzinfo=UTC)
    assert uktime.slot_start("morning", date(2026, 10, 25)) == datetime(2026, 10, 25, 6, 47, tzinfo=UTC)
    assert uktime.slot_start("evening", date(2026, 10, 25)) == datetime(2026, 10, 25, 21, 47, tzinfo=UTC)
    assert uktime.slot_start("morning", date(2027, 3, 28)) == datetime(2027, 3, 28, 5, 47, tzinfo=UTC)


def test_target_card():
    assert uktime.target_card("evening", date(2026, 10, 31)) == date(2026, 11, 1)
    assert uktime.target_card("morning", date(2026, 10, 31)) == date(2026, 10, 31)


def test_hm_and_zone():
    assert uktime.hm(datetime(2026, 10, 15, 16, 30, tzinfo=UTC)) == "17:30"
    assert uktime.hm(datetime(2026, 11, 1, 16, 30, tzinfo=UTC)) == "16:30"
    assert uktime.zone_name(datetime(2026, 10, 15, 12, tzinfo=UTC)) == "BST"
    assert uktime.zone_name(datetime(2026, 11, 1, 12, tzinfo=UTC)) == "GMT"


def test_early_is_only_the_run_up_to_the_slot():
    # GMT: GitHub's 20:47 UTC cron is 20:47 UK, an hour before the board
    assert uktime.early("evening", datetime(2026, 10, 26, 20, 47, tzinfo=UTC))
    assert not uktime.early("evening", datetime(2026, 10, 26, 21, 47, tzinfo=UTC))
    assert uktime.early("morning", datetime(2026, 10, 26, 5, 47, tzinfo=UTC))
    assert not uktime.early("morning", datetime(2026, 10, 26, 6, 47, tzinfo=UTC))
    # BST: the same crons are on time
    assert not uktime.early("evening", datetime(2026, 10, 15, 20, 47, tzinfo=UTC))
    assert not uktime.early("morning", datetime(2026, 10, 15, 5, 47, tzinfo=UTC))
    # a late check after midnight / late morning is not early
    assert not uktime.early("evening", datetime(2026, 10, 27, 0, 40, tzinfo=UTC))
    assert not uktime.early("morning", datetime(2026, 10, 26, 8, 17, tzinfo=UTC))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("uktime_test: OK")
