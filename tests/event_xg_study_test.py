"""backtest/event_xg_study.py (framework #566): game-state correction of match stats, record-only. Offline."""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

import event_xg_study as ex  # noqa: E402
import numpy as np  # noqa: E402

# 1. the regression recovers a known xG-gap effect, and returns None when there is too little data
rng = np.random.default_rng(1)
samples = []
for _ in range(600):
    own, opp = rng.uniform(0.3, 2.5), rng.uniform(0.3, 2.5)
    mean = 5.0
    y = rng.poisson(mean * math.exp(0.15 * (own - opp)))
    samples.append((ex.feats(own, opp, 0.27), float(y), mean))
b = ex.fit_tie(samples)
assert b is not None and 0.08 < b[1] < 0.22, b
assert ex.fit_tie(samples[:10]) is None
assert ex.tied_mean(5.0, 1, 1, 0.27, None) == 5.0
print("ridge Poisson fit: OK")

# 2. pairing needs the same day, league and names; an unpaired match stays unscored
with tempfile.TemporaryDirectory() as d:
    grid = [[0.1, 0.1], [0.4, 0.4]]
    (Path(d) / "picks_2026-11-01.json").write_text(json.dumps({"date": "2026-11-01", "rated": [
        {"league": "L", "home": "Alpha", "away": "Beta", "kickoff": "2026-11-01", "scores": grid, "p": [0.5, 0.3, 0.2]}]}))
    rows = [{"date": "2026-11-01", "league": "L", "home": "Alpha", "away": "Beta", "stats": {}},
            {"date": "2026-11-01", "league": "L", "home": "Gamma", "away": "Delta", "stats": {}},
            {"date": "2026-11-02", "league": "L", "home": "Alpha", "away": "Beta", "stats": {}}]
    got = ex.pair_xg(rows, Path(d))
    assert list(got) == [0] and got[0][1] == 0.3, got
print("pairing: OK")

# 3. empty history reads PENDING, never a number
text, tied = ex.report({"rows": 0, "paired": 0, "res": {}, "from": "PENDING", "to": "PENDING"})
assert "PENDING" in text and tied == []
print("event_xg_study_test: all OK")
