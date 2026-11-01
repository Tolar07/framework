"""Big-Under margin (Architect 2026-11-01, plan point 2): Under 3.5+ needs 5 more points."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import calibration as cal  # noqa: E402

assert cal.under_margin("SB:18|total=4.5|Under 4.5") == cal.UNDER_MARGIN == 0.05
assert cal.under_margin("SB:18|total=5.5|Under 5.5") == 0.05
assert cal.under_margin("SB:18|total=3.5|Under 3.5") == 0.05
assert cal.under_margin("UNDER_3_5") == 0.05
assert cal.under_margin("SB:18|total=2.5|Under 2.5") == 0.0
assert cal.under_margin("SB:18|total=4.5|Over 4.5") == 0.0
assert cal.under_margin("SB:19|total=3.5|Under 3.5") == 0.0, "team totals untouched"
u = cal.model_prob("SB:18|total=5.5|Under 5.5", 0.93)       # 5.5 is not a calibrated line
assert abs(u - 0.88) < 1e-9, u
o, un = cal.model_prob("SB:18|total=4.5|Over 4.5", 0.14), cal.model_prob("SB:18|total=4.5|Under 4.5", 0.86)
assert abs((1 - o) - un - 0.05) < 1e-9, "the Under is the calibrated twin minus the margin"
assert cal.model_prob("SB:18|total=2.5|Under 2.5", 0.5) == 1 - cal.over(2.5, 0.5)
print("under_margin_test: OK")
