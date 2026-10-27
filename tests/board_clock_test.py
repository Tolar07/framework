"""
Offline test of the board clock (monitor/board_clock.py): which slots are due
when, the target card for each, and the start / wait / retry / give-up logic
against a fake GitHub (no network).
"""
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import board_clock as bc


def T(h, m, d=15):
    return datetime(2026, 10, d, h, m, tzinfo=UTC)


# --- due windows and target cards (UK time; BST = UTC+1 until 25 Oct 2026) --
assert bc.due_slots(T(20, 46)) == [], "not before 21:47 UK (20:47 UTC in BST)"
assert bc.due_slots(T(20, 47)) == [("evening", date(2026, 10, 16))], "21:47 UK -> tomorrow's card"
assert bc.due_slots(T(23, 8)) == [("evening", date(2026, 10, 16))], "still due at 00:08 UK"
assert bc.due_slots(T(1, 30, 16)) == [("evening", date(2026, 10, 16))], "after midnight: the evening just past"
assert bc.due_slots(T(3, 47, 16)) == [], "evening window over"
assert bc.due_slots(T(5, 47)) == [("morning", date(2026, 10, 15))], "06:47 UK -> today's card"
assert bc.due_slots(T(9, 46)) == [("morning", date(2026, 10, 15))]
assert bc.due_slots(T(9, 47)) == [], "morning window over"
# GMT from Sunday 25 Oct 2026 (Architect 2026-10-15: "UK time for everything"):
# the slots stay 21:47 / 06:47 on the UK clock, an hour later in UTC.
assert bc.due_slots(T(20, 47, 24)) == [("evening", date(2026, 10, 25))], "Sat 24 Oct: still BST"
assert bc.due_slots(T(5, 47, 25)) == [], "Sun 25 Oct 05:47 UTC = 05:47 GMT: not yet"
assert bc.due_slots(T(6, 47, 25)) == [("morning", date(2026, 10, 25))], "06:47 GMT"
assert bc.due_slots(T(20, 47, 26)) == [], "20:47 GMT: an hour before the board"
assert bc.due_slots(T(21, 47, 26)) == [("evening", date(2026, 10, 27))], "21:47 GMT -> tomorrow's card"
assert bc.due_slots(T(0, 30, 27)) == [("evening", date(2026, 10, 27))], "after midnight GMT: the evening just past"
assert bc.marker("evening", date(2026, 10, 16)) == "output/boards/sent_2026-10-16_evening"
print("due windows + target cards: OK")


class FakeClock(bc.Clock):
    def __init__(self):
        super().__init__("o/r", "t", 99)
        self.sent_markers, self.going, self.started = set(), False, []

    def sent(self, slot, target):
        return (slot, target) in self.sent_markers

    def board_run_going(self):
        return self.going

    def start_board(self, slot, target):
        self.started.append((slot, target))


alerts = []
bc._send = lambda msg: alerts.append(msg)
c = FakeClock()
ev = ("evening", date(2026, 10, 16))
assert c.tick(T(20, 47)) and c.started == [ev], "due, not sent, nothing going -> start it"
c.going = True
assert c.tick(T(20, 48)) == [] and len(c.started) == 1, "a board run going -> wait"
c.going = False
assert c.tick(T(21, 0)) == [] and len(c.started) == 1, "no retry before RETRY_AFTER"
c.tick(T(21, 28))
assert len(c.started) == 2, "run ended without the marker -> retry"
c.sent_markers.add(ev)
assert c.tick(T(22, 30)) == [] and len(c.started) == 2, "marker on main -> done"
print("start / wait / retry / done: OK")

c2 = FakeClock()
for k in range(5):
    c2.tick(T(20, 47) + k * timedelta(minutes=41))
assert len(c2.started) == bc.MAX_TRIES and len(alerts) == 1 and "Run workflow" in alerts[0], \
    "after MAX_TRIES the Architect is told exactly what to start, once"
print("give up after MAX_TRIES with one alert: OK")

wf = (Path(__file__).parent.parent / ".github/workflows/clock.yml").read_text(encoding="utf-8")
assert "monitor/board_clock.py" in wf and "actions: write" in wf and "timeout-minutes: 355" in wf
assert timedelta(minutes=355) > bc.HANDOFF_AFTER
print("clock.yml wiring: OK")

print("\n✅ ALL BOARD CLOCK TESTS PASSED")
