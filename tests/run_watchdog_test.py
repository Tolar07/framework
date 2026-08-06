"""Run watchdog tests.

The watchdog is the instrument that notices when the daily run DIDN'T happen:
missing log = Python never started, no 'run completed OK' = crashed mid-run,
no Telegram delivery line = board never reached the phone. All three must
alert; a complete delivered run must stay silent."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor.run_watchdog import check_run_log, verify

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_watchdog_"))


# --- 1. missing log -> Python never started -----------------------------------
ok, reasons = check_run_log(_tmp / "daily_2026-08-06.log")
assert ok is False and any("never started" in r for r in reasons), reasons
print("1. missing log flagged (Python never started): OK")

# --- 2. complete delivered run -> OK ------------------------------------------
p = _tmp / "daily_2026-08-06.log"
p.write_text("[x] run_daily.py STARTED\n"
             "[x] delivered 1 part(s) to Telegram\n"
             "[x] run completed OK\n", encoding="utf-8")
ok, reasons = check_run_log(p)
assert ok is True and not reasons
print("2. complete + delivered run passes: OK")

# --- 3. started but never completed -> flagged --------------------------------
p = _tmp / "daily_2026-08-07.log"
p.write_text("[x] run_daily.py STARTED\n[x] scan Eredivisie\n", encoding="utf-8")
ok, reasons = check_run_log(p)
assert ok is False and any("did not finish" in r for r in reasons), reasons
print("3. crash mid-run flagged: OK")

# --- 4. completed but Telegram not delivered -> flagged -----------------------
p = _tmp / "daily_2026-08-08.log"
p.write_text("[x] run completed OK\n[x] WHATSAPP_* not set — skipped\n",
             encoding="utf-8")
ok, reasons = check_run_log(p)
assert ok is False and any("to Telegram" in r for r in reasons), reasons
print("4. board built but phone not reached -> flagged: OK")

# --- 5. verify() alerts via stub notifier, never raises -----------------------
# Use a date with NO log (2026-08-09) so the alert path fires.
sent = {"n": 0}
def stub(body):
    sent["n"] += 1
    assert "did NOT happen" in body and "2026-08-09" in body
    return True, ["stub delivered"]

complete, notes = verify("2026-08-09", _tmp, notify_fn=stub)
assert complete is False and sent["n"] == 1
assert any("ALERT sent" in n for n in notes), notes
print("5. verify() sends one alert when run missing: OK")

# --- 6. alert failure never crashes the watchdog ------------------------------
def fail(body):
    raise RuntimeError("telegram down")
complete, notes = verify("2026-08-09", _tmp, notify_fn=fail)
assert complete is False
assert any("continues" in n for n in notes), notes
print("6. alert delivery failure does not crash watchdog: OK")

# --- 7. complete run -> verify() is silent (no alert) -------------------------
complete, notes = verify("2026-08-06", _tmp, notify_fn=stub)  # complete log from #2
assert complete is True and sent["n"] == 1, "no extra alert on a good run"
print("7. good run alerts nothing: OK")

print("\n✅ ALL RUN WATCHDOG TESTS PASSED")
