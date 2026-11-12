"""monitor/edge_candidates.py: a study's EDGE CANDIDATE opens one build issue, once. Offline."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor import edge_candidates as ec  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    study = d / "study.json"
    c = {"venue": "SportyBet", "market": "goals over 2.5", "side": "no", "gap": 0.08, "disc_n": 300, "disc_roi": 0.04,
         "hold_n": 250, "hold_roi": 0.06, "hold_lo": 0.01, "hold_hi": 0.11}
    study.write_text(json.dumps({"candidates": [c]}))
    src = {"football trend atlas": (study, "backtest/trend_atlas_study.py"), "missing": (d / "none.json", "x")}
    opened = []

    def opener(t, b):
        opened.append((t, b))
        return "https://example/1"

    out = ec.run(src, d / "seen.json", opener=opener)
    assert "1 new issue" in out and len(opened) == 1, out
    t, b = opened[0]
    assert "goals over 2.5 NO" in t and "+6.0%" in b and "SHADOW" in b and "Architect" in b
    out = ec.run(src, d / "seen.json", opener=opener)            # same candidate again: no second issue
    assert "0 new issue" in out and len(opened) == 1, out
    study.write_text(json.dumps({"candidates": []}))
    out = ec.run(src, d / "seen.json", opener=opener)
    assert "1 earlier candidate(s) not found" in out, out
    seen = json.loads((d / "seen.json").read_text())
    assert list(seen.values())[0]["issue"] == "https://example/1"
print("edge_candidates_test OK")
