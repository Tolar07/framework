"""Gate-telemetry tests — the 'road to the gate' numbers in /stats.

leg_telemetry() turns the logged legs into an honest trajectory: how many
settled legs earn a closing line (capture rate), the observed legs-per-day,
and a projected days-to-gate. Rates that cannot be stated are None, never
guessed (HR35)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.store import Brain
from clv.clv_logger import CLVLog

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_gate_"))


def _seed(brain: Brain, clv_path: Path) -> None:
    """8 legs over 4 days; 5 settled, 4 with a closing line (CLV)."""
    log = CLVLog(path=clv_path)
    legs = []
    for i in range(8):
        leg = log.log_entry(league="Eredivisie", fixture=f"H{i} v A{i}",
                            market="1X2_HOME", model_prob=0.5, entry_odds=2.0)
        if i < 5:  # settle the first five
            if i < 4:  # four of them also get a closing line -> CLV
                log.log_close(leg.leg_id, closing_odds=1.8)
            log.log_result(leg.leg_id, ft_result="1-0", hit=(i % 2 == 0))
    brain.sync_legs([clv_path])
    # Spread date_logged across a 4-day window to exercise the rate math.
    dates = ["2026-08-0" + str(d) for d in range(1, 5)]  # 1..4
    rows = brain.leg_rows()
    for idx, (leg_id,) in enumerate(rows):
        brain.set_leg_date(leg_id, dates[idx % 4])


# --- 1. full trajectory -------------------------------------------------------
b = Brain(_tmp / "t.db")
_seed(b, _tmp / "clv.json")
tm = b.leg_telemetry()
assert tm["n_legs"] == 8, tm
assert tm["n_with_clv"] == 4, tm
assert tm["n_settled"] == 5, tm
assert tm["clv_capture_rate"] == 0.8, f"4/5 settled capture -> {tm}"
assert tm["legs_per_day"] == 2.0, f"8 legs over 4 days -> {tm}"
assert abs(tm["clv_legs_per_day"] - 1.6) < 1e-9, tm
assert abs(tm["days_to_gate"] - (30 - 4) / 1.6) < 0.2, tm
print("1. full trajectory (8 legs, 4 CLV, rate + projection): OK")

# --- 2. no settled legs -> honest NO DATA, never a guess ----------------------
b2 = Brain(_tmp / "t2.db")
tm2 = b2.leg_telemetry()
assert tm2["n_legs"] == 0 and tm2["clv_capture_rate"] is None
assert tm2["days_to_gate"] is None, "no production -> no projection"
print("2. empty ledger -> capture NO DATA, projection None: OK")

# --- 3. settled but no closing lines -> capture 0, projection None ------------
# Seed 3 legs, settle all 3, close NONE -> capture_rate 0.0, days_to_gate None.
b3 = Brain(_tmp / "t3.db")
log3 = CLVLog(path=_tmp / "clv3.json")
for i in range(3):
    leg = log3.log_entry(league="La Liga", fixture=f"R{i} v S{i}",
                         market="OVER_2_5", model_prob=0.5, entry_odds=2.0)
    log3.log_result(leg.leg_id, ft_result="2-1", hit=True)
b3.sync_legs([_tmp / "clv3.json"])
tm3 = b3.leg_telemetry()
assert tm3["clv_capture_rate"] == 0.0, tm3
assert tm3["days_to_gate"] is None, "zero CLV production cannot project"
print("3. settled-without-closing-lines -> capture 0, projection None: OK")

print("\n✅ ALL GATE TELEMETRY TESTS PASSED")
