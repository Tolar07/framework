"""BTTS singles also go out as 2-3 leg accas (Architect 2026-11-03)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from output.produce_bet import _btts_groups, _build_btts_accas  # noqa: E402

assert _btts_groups(0) == [] and _btts_groups(1) == []
assert _btts_groups(2) == [2] and _btts_groups(3) == [3]
assert _btts_groups(4) == [2, 2] and _btts_groups(5) == [3, 2]
assert _btts_groups(6) == [3, 3] and _btts_groups(7) == [3, 2, 2] and _btts_groups(8) == [3, 3, 2]
for n in range(2, 20):
    g = _btts_groups(n)
    assert sum(g) == n and all(x in (2, 3) for x in g), (n, g)

singles = [(f"BTTS {i}", [(f"bf{i}", "Both teams to score — yes", c, "BTTS_YES", 1.7)], c)
           for i, c in enumerate([0.62, 0.60, 0.57, 0.55, 0.52], 1)]
accas = _build_btts_accas(singles)
assert [n for n, _, _ in accas] == ["BTTS acca 1", "BTTS acca 2"]
assert [len(l) for _, l, _ in accas] == [3, 2]
assert [leg[0] for leg in accas[0][1]] == ["bf1", "bf2", "bf3"], "strongest singles first"
assert {leg[0] for _, l, _ in accas for leg in l} == {f"bf{i}" for i in range(1, 6)}, "each game once"
assert abs(accas[1][2] - 0.55 * 0.52) < 1e-9
print("btts_accas_test: OK")
