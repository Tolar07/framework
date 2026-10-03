"""Dead-man's-switch tests — verifies the 07:00 run completeness check."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor.dead_mans_switch import check_today_complete, verify, alert_text

_tmp = Path(tempfile.mkdtemp(prefix="olp_deadmans_"))
_logs = _tmp / "logs"
_logs.mkdir()


def _write_log(text: str) -> Path:
    today = __import__("datetime").date.today().isoformat()
    log_path = _logs / f"daily_{today}.log"
    log_path.write_text(text, encoding="utf-8")
    return log_path


# --- 1. Missing log -> incomplete ---------------------------------------------
complete, reasons = check_today_complete(_logs)
assert not complete
assert "never started" in reasons[0]
print("1. missing log -> incomplete: OK")


# --- 2. Log exists but no 'run completed OK' ----------------------------------
_write_log("[2026-08-07T07:00:00] run_daily.py STARTED\n[2026-08-07T07:00:30] some error")
complete, reasons = check_today_complete(_logs)
assert not complete
assert any("did not finish" in r for r in reasons)
print("2. log exists but no 'run completed OK' -> incomplete: OK")


# --- 3. 'run completed OK' but no Telegram delivery ---------------------------
_write_log("[2026-08-07T07:00:00] run_daily.py STARTED\n[2026-08-07T07:00:30] run completed OK")
complete, reasons = check_today_complete(_logs)
assert not complete
assert any("did not reach the phone" in r for r in reasons)
print("3. 'run completed OK' but no Telegram delivery -> incomplete: OK")


# --- 4. Complete and delivered ------------------------------------------------
_write_log("[2026-08-07T07:00:00] run_daily.py STARTED\n[2026-08-07T07:00:30] run completed OK\n[2026-08-07T07:00:31] delivered 3 part(s) to Telegram")
complete, reasons = check_today_complete(_logs)
assert complete
assert not reasons
print("4. complete and delivered -> OK: OK")


# --- 5. alert_text renders correctly ------------------------------------------
text = alert_text("2026-08-07", ["no log", "no delivery"])
assert "DEAD-MAN'S-SWITCH" in text
assert "2026-08-07" in text
assert "no log" in text
assert "no delivery" in text
assert "08:00 dead-man's-switch" in text
print("5. alert_text renders correctly: OK")


# --- 6. verify() with mocked alert_dispatcher (primary path) -------------------
# Need a fresh log dir for missing log test
_logs2 = _tmp / "logs2"
_logs2.mkdir()
# Primary path: alert_dispatcher.dispatch_alert returns results dict
with patch("monitor.dead_mans_switch.alert_dispatcher.dispatch_alert",
           return_value={"telegram": (True, "ok"), "email": (False, "no config"), "webhook": (False, "no config")}):
    complete, notes = verify(_logs2)
    assert not complete  # missing log
    assert any("ALERT dispatched" in n for n in notes)
print("6. verify() with mocked alert_dispatcher: OK")


# --- 7. verify() success path -------------------------------------------------
_write_log("[2026-08-07T07:00:00] run_daily.py STARTED\n[2026-08-07T07:00:30] run completed OK\n[2026-08-07T07:00:31] delivered 3 part(s) to Telegram")
complete, notes = verify(_logs)
assert complete
assert any("OK" in n for n in notes)
print("7. verify() success path: OK")


# --- 8. alert delivery failure doesn't crash ----------------------------------
_write_log("[2026-08-07T07:00:00] run_daily.py STARTED\n[2026-08-07T07:00:30] run completed OK")  # no delivery
# alert_dispatcher throws, notify fallback throws -> should not crash
with patch("monitor.dead_mans_switch.alert_dispatcher.dispatch_alert",
           side_effect=RuntimeError("dispatcher down")):
    complete, notes = verify(_logs, notify_fn=lambda m: (_ for _ in ()).throw(RuntimeError("telegram down")))
assert not complete
# With the new architecture, both dispatcher and fallback fail -> note contains "failed"
assert any("failed" in n.lower() or "raised" in n.lower() for n in notes)
print("8. alert delivery failure doesn't crash: OK")


print("\nALL DEAD-MAN'S-SWITCH TESTS PASSED")