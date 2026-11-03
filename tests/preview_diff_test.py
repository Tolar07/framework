"""Preview boards: what changed between two looks (Architect 2026-11-03)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from monitor import preview_diff as pd  # noqa: E402

S = lambda fx, mk, pr, ch, news="OK": {"fixture": fx, "market": mk, "pick": mk, "price": pr,  # noqa: E731
                                       "chance": ch, "news_level": news}
old = {"singles": [S("A v B", "DC_12", 1.30, 0.78), S("C v D", "O15", 1.25, 0.80), S("E v F", "DC_1X", 1.40, 0.75)],
       "accas": [{}]}
new = {"singles": [S("A v B", "DC_12", 1.36, 0.78), S("C v D", "O15", 1.25, 0.80, "RISK"), S("G v H", "O15", 1.30, 0.79)],
       "accas": [{}, {}]}
out = pd.changes(old, new)
assert any(x.startswith("+ G v H") for x in out)
assert any(x.startswith("- E v F") for x in out)
assert any("price 1.30 -> 1.36" in x for x in out)
assert any(x.startswith("! C v D: news OK -> RISK") for x in out)
assert any("accas: 1 -> 2" in x for x in out)
assert pd.changes(old, old) == []
print("preview_diff_test: OK")
