"""Missed-run watchdog: alerts only when no daily board run succeeded."""
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import run_watchdog as wd  # noqa: E402

START = datetime(2026, 10, 3, 18, 0, tzinfo=UTC)


def run(created, status="completed", conclusion="success"):
    return {"created_at": created, "status": status, "conclusion": conclusion}


def test_success_in_window_is_ok():
    ok, _ = wd.check_runs([run("2026-10-03T20:48:00Z")], START)
    assert ok


def test_no_runs_alerts():
    ok, reason = wd.check_runs([], START)
    assert not ok and "no daily board run" in reason
    assert wd.alert_needed(ok, reason)


def test_success_before_window_does_not_count():
    ok, reason = wd.check_runs([run("2026-10-03T05:48:00Z")], START)
    assert not ok and wd.alert_needed(ok, reason)


def test_failure_only_is_not_realerted():
    ok, reason = wd.check_runs([run("2026-10-03T20:48:00Z", conclusion="failure")], START)
    assert not ok and not wd.alert_needed(ok, reason)


def test_in_progress_alerts():
    ok, reason = wd.check_runs([run("2026-10-03T22:50:00Z", "in_progress", None)], START)
    assert not ok and "not finished" in reason and wd.alert_needed(ok, reason)


def test_window_start_per_slot():
    now = datetime(2026, 10, 3, 23, 17, tzinfo=UTC)
    assert wd.window_start("evening", now).hour == 18
    assert wd.window_start("morning", now.replace(hour=8)).hour == 3


def test_alert_text_names_slot_and_link():
    t = wd.alert_text("evening", "no daily board run started at all", "Tolar07/framework")
    assert "evening" in t and "actions/workflows/daily.yml" in t


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("run_watchdog_test: OK")
