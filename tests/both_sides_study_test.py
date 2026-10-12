"""Both sides study: every side is a yes/no record; learning is gated like engine/learning.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import both_sides_study as bs  # noqa: E402

row = {"first": {"p": {"1x2": [2.0, 3.4, 4.0], "btts": [1.8, 1.95], "dc": [1.25, 1.33, 1.8]}},
       "result": {"h": 1, "a": 0}}
recs = bs.records(row)
keys = {r["key"]: r for r in recs}
assert {"btts:yes", "btts:no", "1x2:home", "1x2:draw", "1x2:away", "dc:1x", "dc:12", "dc:x2"} <= set(keys)
assert keys["btts:no"]["won"] == 1 and keys["btts:yes"]["won"] == 0, "both sides of BTTS are records"
assert abs(keys["btts:yes"]["fair"] + keys["btts:no"]["fair"] - 1) < 1e-9
assert abs(sum(keys[k]["fair"] for k in ("dc:1x", "dc:12", "dc:x2")) - 2) < 1e-9, "double chance covers each result twice"
assert bs.band(1.25) == "1.20-1.40" and bs.band(3.5) == "3.00+"

# too few records: nothing learned; many records far off: a capped shift
few = [{"seg": "s", "won": 1, "fair": 0.5}] * 10
assert bs.learn(few) == {}
many = [{"seg": "s", "won": 1, "fair": 0.5}] * 200
assert 0 < bs.learn(many)["s"] <= bs.MAX_SHIFT
print("both_sides_study_test: OK")
