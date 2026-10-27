"""Missed-run watchdog: starts the slot's board only when no daily board run
succeeded, failed or is still going in the slot's window."""
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import run_watchdog as wd  # noqa: E402

# The evening slot is 21:47 UK = 20:47 UTC in BST; the window opens 10 min before.
START = datetime(2026, 10, 3, 20, 37, tzinfo=UTC)


def run(created, status="completed", conclusion="success"):
    return {"created_at": created, "status": status, "conclusion": conclusion}


def test_success_in_window_is_ok():
    state, _ = wd.check_runs([run("2026-10-03T20:48:00Z")], START)
    assert state == wd.OK


def test_no_runs_is_missed():
    state, reason = wd.check_runs([], START)
    assert state == wd.MISSED and "no daily board run" in reason


def test_success_before_window_does_not_count():
    state, _ = wd.check_runs([run("2026-10-03T05:48:00Z")], START)
    assert state == wd.MISSED


def test_failure_is_left_to_dailys_own_alert():
    state, _ = wd.check_runs([run("2026-10-03T20:48:00Z", conclusion="failure")], START)
    assert state == wd.FAILED


def test_cancelled_or_timed_out_is_missed():
    # A run killed by its 45-minute timeout ends 'cancelled'; daily.yml's
    # failure() alert does not fire for that, so the watchdog must.
    state, reason = wd.check_runs([run("2026-10-03T20:48:00Z", conclusion="cancelled")], START)
    assert state == wd.MISSED and "cancelled" in reason


def test_run_still_going_is_left_alone():
    state, reason = wd.check_runs([run("2026-10-03T22:50:00Z", "in_progress", None)], START)
    assert state == wd.RUNNING and "not finished" in reason


def test_window_start_per_slot():
    now = datetime(2026, 10, 3, 23, 17, tzinfo=UTC)
    assert wd.window_start("evening", now) == START
    assert wd.window_start("morning", now.replace(hour=8)) == datetime(2026, 10, 3, 5, 37, tzinfo=UTC)


def test_evening_check_after_midnight_looks_at_the_evening_just_past():
    # GitHub fired this repo's crons 3-5 h late on 2026-10-02/03; a 23:17
    # check landing at 00:40 must not look at a window that starts tonight.
    late = datetime(2026, 10, 4, 0, 40, tzinfo=UTC)
    start = wd.window_start("evening", late)
    assert start == START
    assert wd.target_date("evening", start) == date(2026, 10, 4)


def test_target_date_matches_daily_yml():
    assert wd.target_date("evening", START) == date(2026, 10, 4)   # tomorrow's card
    morning = datetime(2026, 10, 3, 3, 0, tzinfo=UTC)
    assert wd.target_date("morning", morning) == date(2026, 10, 3)  # today's card


def test_winter_window_follows_the_uk_clock():
    # From 25 Oct 2026 the UK is on GMT: 21:47 UK = 21:47 UTC.
    now = datetime(2026, 10, 26, 23, 17, tzinfo=UTC)
    start = wd.window_start("evening", now)
    assert start == datetime(2026, 10, 26, 21, 37, tzinfo=UTC)
    assert wd.target_date("evening", start) == date(2026, 10, 27)
    # daily.yml's BST cron fires at 20:47 UTC, an hour early in GMT, and ends at
    # its UK-time gate with 'success' having sent nothing: it is not the board.
    state, _ = wd.check_runs([run("2026-10-26T20:48:00Z")], start)
    assert state == wd.MISSED


class _Patch:
    """Swap watchdog/notify functions for one test; restore afterwards."""

    def __init__(self, runs=None, fetch_error=None, start_error=None):
        self.sent, self.started = [], []
        self._saved = (wd.fetch_runs, wd.start_board, wd.notify.send_telegram)

        def fetch(repo, token, since):
            if fetch_error:
                raise fetch_error
            return runs or []

        def start(repo, token, slot, day):
            if start_error:
                raise start_error
            self.started.append((slot, day))

        def send(body, *a, **k):
            self.sent.append(body)
            return True, []

        wd.fetch_runs, wd.start_board, wd.notify.send_telegram = fetch, start, send

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        wd.fetch_runs, wd.start_board, wd.notify.send_telegram = self._saved


NOW = datetime(2026, 10, 3, 23, 17, tzinfo=UTC)


def test_missed_slot_is_started_with_its_own_slot_and_day():
    with _Patch() as p:
        code = wd.main(["--slot", "evening"], now=NOW)
    assert code == 0
    assert p.started == [("evening", date(2026, 10, 4))]
    assert len(p.sent) == 1 and "Started it now" in p.sent[0] and "2026-10-04" in p.sent[0]


def test_start_refused_gives_exact_manual_inputs():
    with _Patch(start_error=RuntimeError("HTTP 403")) as p:
        code = wd.main(["--slot", "morning"], now=NOW.replace(hour=8))
    assert code == 1 and not p.started
    assert "HTTP 403" in p.sent[0] and "day 2026-10-03 and slot morning" in p.sent[0]


def test_ok_running_and_failed_send_nothing():
    for runs in ([run("2026-10-03T20:48:00Z")],
                 [run("2026-10-03T23:10:00Z", "queued", None)],
                 [run("2026-10-03T20:48:00Z", conclusion="failure")]):
        with _Patch(runs=runs) as p:
            assert wd.main(["--slot", "evening"], now=NOW) == 0
        assert not p.started and not p.sent


def test_early_check_in_winter_does_nothing():
    # GMT: the 21:23 UTC check is 21:23 UK, before the 21:47 UK board.
    with _Patch() as p:
        assert wd.main(["--slot", "evening"], now=datetime(2026, 10, 26, 21, 23, tzinfo=UTC)) == 0
        assert wd.main(["--slot", "morning"], now=datetime(2026, 10, 27, 6, 23, tzinfo=UTC)) == 0
    assert not p.started and not p.sent


def test_winter_missed_slot_is_started_for_the_uk_card():
    with _Patch(runs=[run("2026-10-26T20:48:00Z")]) as p:
        assert wd.main(["--slot", "evening"], now=datetime(2026, 10, 26, 22, 23, tzinfo=UTC)) == 0
    assert p.started == [("evening", date(2026, 10, 27))] and "22:23 UK time" in p.sent[0]


def test_unreadable_history_alerts_without_starting():
    with _Patch(fetch_error=OSError("timed out")) as p:
        assert wd.main(["--slot", "evening"], now=NOW) == 1
    assert not p.started and "could not read run history" in p.sent[0]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("run_watchdog_test: OK")
