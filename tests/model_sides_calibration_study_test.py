"""Model sides calibration study (framework #377): walk-forward, no look-ahead, PENDING with no data."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import model_sides_calibration_study as cs  # noqa: E402

assert any("PENDING" in x for x in cs.report([])), "no data reads PENDING"

random.seed(1)
ch = [0.8] * 400
won = [1 if random.random() < 0.6 else 0 for _ in ch]
a, b = cs.fit_platt(ch, won)
assert abs(cs._sig(a + b * cs._logit(0.8)) - 0.6) < 0.05, "Platt recovers a known bias"


def mk(day, i):
    return {"date": f"2026-10-{day:02d}", "fixture": f"f{i}", "key": "k", "market": "Over/Under",
            "side": "Under 2.5", "chance": 0.8, "price": 1.5, "won": int(random.random() < 0.6)}


recs = [mk(d, i) for d in range(1, 21) for i in range(10)]
wf = cs.walk_forward(recs, train_days=60, min_n=50)
early = [r for r in wf if r["date"] <= "2026-10-05"]
assert all(not r["used"] and r["cal"] == r["chance"] for r in early), "no history -> raw, never look-ahead"
late = [r for r in wf if r["used"]]
assert late and all(r["cal"] < 0.78 for r in late), "over-rated side is pulled down"
s = cs.score(late)
assert s["brier_cal"] < s["brier_raw"] and cs.verdict(s).startswith("KEEP")
assert cs.verdict({"n": 10, "brier_raw": .2, "brier_cal": .21, "roi_raw": 0, "roi_cal": 0}).startswith("REJECT")
print("model_sides_calibration_study_test: OK")
