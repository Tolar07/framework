"""Telegram alert gate (Architect 2026-08-11). No network.

The bot pushes ONLY the daily run and command responses. Monitor alerts
(health, watchdog, dead-man's-switch) keep logging locally but must NOT
message Telegram unless TELEGRAM_ALERTS_ENABLED=1 is set. The daily run's
deliver() path is deliberately unaffected by the gate."""
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import notify


def _clear() -> None:
    os.environ.pop("TELEGRAM_ALERTS_ENABLED", None)


# --- 1. gate off by default: nothing sent, honest note ------------------------
_clear()
with mock.patch.object(notify, "send_telegram") as st:
    ok, notes = notify.send_alert("🚨 test alert")
assert ok is False, "alert must not be sent when the gate is off"
assert not st.called, "send_telegram must not be called with the gate off"
assert any("TELEGRAM_ALERTS_ENABLED" in n for n in notes), notes
print("1. gate off by default — alert logged locally, nothing sent: OK")

# --- 2. gate on -> routes through send_telegram -------------------------------
os.environ["TELEGRAM_ALERTS_ENABLED"] = "1"
with mock.patch.object(notify, "send_telegram",
                       return_value=(True, ["sent"])) as st:
    ok, _ = notify.send_alert("🚨 test alert")
assert ok is True
assert st.called, "send_telegram must be called when the gate is on"
print("2. TELEGRAM_ALERTS_ENABLED=1 -> routes to send_telegram: OK")

# --- 3. only 1/true enable; anything else is off ------------------------------
for value, expected in (("true", True), ("True", True),
                        ("0", False), ("yes", False), ("", False), ("2", False)):
    os.environ["TELEGRAM_ALERTS_ENABLED"] = value
    with mock.patch.object(notify, "send_telegram",
                           return_value=(True, ["sent"])) as st:
        ok, _ = notify.send_alert("x")
    assert st.called is expected, f"value={value!r} expected called={expected}"
print("3. accepted values are 1/true only: OK")

# --- 4. the DAILY RUN path (deliver -> send_telegram) is NOT gated ------------
_clear()
with mock.patch.object(notify, "send_telegram",
                       return_value=(True, ["sent"])) as st:
    ok, _ = notify.deliver("daily board body", save_to=None)
assert st.called, "the daily run must still send even with the gate off"
print("4. daily-run deliver() bypasses the alert gate: OK")

print()
print("✅ ALL TELEGRAM ALERT-GATE TESTS PASSED")
