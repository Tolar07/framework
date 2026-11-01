"""Model sides study (Architect 2026-11-01): every side of every market, paper, at the model's chance."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import model_sides_study as ms  # noqa: E402

g = ms.grid([[0.05, 0.10, 0.05], [0.10, 0.30, 0.10], [0.05, 0.10, 0.15]])
assert g is not None and abs(g.sum() - 1) < 1e-9
yes, no = ms.chance("SB:29||Yes", g), ms.chance("SB:29||No", g)
assert abs(yes + no - 1) < 1e-9, "both BTTS sides are priced and add to 1"
over, under = ms.chance("SB:18|total=2.5|Over 2.5", g), ms.chance("SB:18|total=2.5|Under 2.5", g)
assert abs(over + under - 1) < 1e-9
h, d, a = (ms.chance(f"SB:1||{x}", g) for x in ("Home", "Draw", "Away"))
assert abs(h + d + a - 1) < 1e-9
assert ms.market_of("SB:19|total=1.5|Over 1.5") == "Home Team Goals"

picks = {"rated": [{"fixture": "Hull v Ipswich", "home": "Hull", "away": "Ipswich", "src": "model",
                    "scores": [[0.05, 0.10, 0.05], [0.10, 0.30, 0.10], [0.05, 0.10, 0.15]]}]}
games = [{"id": "sr:match:1", "home": "Hull City", "away": "Ipswich Town", "result": {"h": 2, "a": 2},
          "last": {"p": {"ladder": {"SB:29||Yes": 1.7, "SB:29||No": 2.0, "SB:18|total=2.5|Over 2.5": 1.8,
                                    "SB:18|total=2.5|Under 2.5": 1.9}}}}]
recs = ms.records("2026-11-01", picks, games)
keys = {r["key"]: r for r in recs}
assert all(r["chance"] >= 0.50 for r in recs) and recs, recs
assert ("SB:29||Yes" in keys) != ("SB:29||No" in keys), "the side the model favours, whichever it is"
assert all(r["won"] == (r["key"] in ("SB:29||Yes", "SB:18|total=2.5|Over 2.5")) for r in recs)
L = ms.report(recs, ["2026-11-01"])
assert any(x.startswith("| 50% |") for x in L)
print("model_sides_study_test: OK")
