"""
Offline test of the pre-kickoff loop's timing (monitor/news_loop.py): rounds
every 20 minutes 09:00-20:40 UTC, a hand-off before GitHub's 6-hour job
limit, no idle wait longer than EARLIEST, and the workflows that start it.
"""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import news_loop as nl  # noqa: E402


def t(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 10, 5, h, m, s, tzinfo=UTC)


# Window and rounds
assert not nl.in_window(t(8, 59)) and nl.in_window(t(9, 0)) and nl.in_window(t(20, 40, 30))
assert not nl.in_window(t(20, 42)) and nl.finished(t(20, 42)) and not nl.finished(t(20, 40))
assert nl.next_round(t(5, 52)) == t(9, 0), "before the window: wait for 09:00"
assert nl.next_round(t(9, 0, 5)) == t(9, 20)
assert nl.next_round(t(9, 19)) == t(9, 20)
assert nl.next_round(t(9, 20)) == t(9, 40), "a round just done is not repeated"
assert nl.next_round(t(20, 40, 10)) == t(21, 0) and nl.finished(t(21, 0))

# Every round of a full day, as the loop walks it from the morning board
rounds, now = [], t(9, 0)
while not nl.finished(now):
    rounds.append(now)
    now = nl.next_round(now)
assert len(rounds) == 36 and rounds[-1] == t(20, 40), (len(rounds), rounds[-1])

# Hand-off: never sleep past the job limit; the chain covers the whole day
started = t(5, 52)
assert not nl.should_hand_off(started, t(5, 52), t(9, 0)), "3 h wait for the window is fine"
assert not nl.should_hand_off(started, t(11, 0), t(11, 20)), "5 h 28 m: keep going"
assert nl.should_hand_off(started, t(11, 20), t(11, 40)), "5 h 48 m: hand off"
assert not nl.should_hand_off(t(16, 0), t(20, 40), t(21, 0)), "after the last round: just end"
assert nl.HANDOFF_AFTER + timedelta(minutes=nl.EVERY_MIN) < timedelta(minutes=355), \
    "the last round before a hand-off ends inside the job's timeout"
assert nl.EARLIEST < nl.HANDOFF_AFTER, "an early start never waits past the job limit"

# The workflows that run and start it
news = (ROOT / ".github/workflows/news.yml").read_text(encoding="utf-8")
daily = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
assert "monitor/news_loop.py" in news and "actions: write" in news and "timeout-minutes: 355" in news
assert "TELEGRAM_SUBSCRIBER_CHAT_IDS" in news, "order 33: subscribers get the alerts"
assert "actions/workflows/news.yml/dispatches" in daily and "actions: write" in daily, \
    "the board run starts the loop"
_start = daily.split("- name: Start the pre-kickoff loop")[1].split("- name:")[0]
assert "|| code=000" in _start and "exit 1" not in _start, "starting the loop never fails the board run"
print("✅ news loop timing + wiring: OK")
