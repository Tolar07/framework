"""Positive-CLV accas (engine/clv_accas.py, Architect 2026-10-21). Offline."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import clv_accas as ca

with tempfile.TemporaryDirectory() as d:
    singles = ([{"market": "DC_1X", "clv": 0.4}] * 60 + [{"market": "SB:16|hcp=-1|Home", "clv": -0.5}] * 60
               + [{"market": "OVER_1_5", "clv": 2.0}] * 10)
    (Path(d) / "picks_2026-10-10.json").write_text(json.dumps({"date": "2026-10-10", "singles": singles}))
    (Path(d) / "picks_2026-10-21.json").write_text(json.dumps({"date": "2026-10-21", "singles": singles}))
    st = ca.family_clv(Path(d), "2026-10-21")
    assert st["Double chance"] == {"n": 60, "clv": 0.004}, st          # percent -> fraction; today excluded
    assert ca.positive_families(st) == {"Double chance"}, "negative or thin families never count"


def bf(i, key, p):
    return NS(fixture=f"H{i} v A{i} (La Liga)", best_market_key=key, best_model_prob=p,
              probs=NS(home_team=f"H{i}", away_team=f"A{i}"))


deploy = [bf(i, "DC_1X", 0.70 + i / 100) for i in range(9)] + [bf(20, "SB:16|hcp=-1|Home", 0.95)]
slips = ca.build(deploy, st)
assert [n for n, _l, _c in slips] == ["CLV acca A", "CLV acca B"]
assert [len(l) for _n, l, _c in slips] == [4, 4], "max 4 legs, 2 slips; the ninth leg is left over"
assert abs(slips[0][1][0][2] - 0.78) < 1e-9, "the likeliest leg first"
assert all(b.best_market_key == "DC_1X" for _n, l, _c in slips for b, _p, _q in l), "only positive-CLV families"
assert ca.build(deploy[:2], st) == [], "fewer than 3 legs: no acca"
assert "Double chance +0.40% over 60" in ca.note(st, slips)
print("clv accas: OK")
