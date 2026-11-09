"""Second-half inputs (Architect 2026-11-09): first meeting, table gaps, stakes — this season, before the day only."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import second_half_study as st  # noqa: E402
from engine import inputs as ip  # noqa: E402

teams = ["A", "B", "C", "D", "E", "F", "G", "H"]
ms, d = [], 0
for i, h in enumerate(teams):               # first half: everyone once, A best, H worst
    for j, a in enumerate(teams):
        if i < j:
            d += 1
            ms.append({"date": (date(2025, 9, 1) + timedelta(days=2 * d)).isoformat(),
                       "home": h, "away": a, "hg": 2, "ag": 0})
H = ip.History(ms)
day = "2026-01-10"
f = ip.second_half(H, "B", "A", day)
assert f["rev_gd"] == -2.0 and f["rev_goals"] == 2.0, f    # A beat B 2-0 at A's ground: -2 from B's view
assert f["half_ppg_gap"] < 0 and f["half_gd_gap"] < 0, f
assert f["motive_gap"] is not None and f["dead_count"] is not None, f
assert ip.second_half(H, "B", "A", "2025-09-15")["rev_gd"] is None, "first half: nothing until everyone met once"
assert ip.second_half(H, "B", "A", "2026-08-15")["half_ppg_gap"] is None, "a new season starts from nothing"
t = ip.table_asof(H, day)
s = ip.stakes(t, "A")
assert s["games_left"] == 7 and "title" in s["lines"], s   # 7 points clear, 21 left: still catchable
print("second-half inputs: first meeting, gaps, stakes, this season only: OK")

t2 = {k: dict(v) for k, v in t.items()}
for k in t2:
    t2[k]["played"] = 13
t2["D"]["pts"], t2["E"]["pts"] = 40, 10
ranks = sorted(t2, key=lambda k: -t2[k]["pts"])
for r, k in enumerate(ranks, 1):
    t2[k]["rank"] = r
assert ip.stakes(t2, "D")["games_left"] == 1
print("stakes with one game left: OK")

assert st.devig([2.0, 4.0, 4.0]) == [0.5, 0.25, 0.25]
assert st.devig([2.0, None, 3.0]) is None
scored = [("d", 0.5, 0.6, 1, {"open": 2.0, "close": 1.9}), ("d", 0.5, 0.6, 0, {"open": 2.0, "close": 1.9})]
mo = st.money(scored)
assert mo["market"]["bets"] == 0 and mo["with_feature"]["bets"] == 2 and mo["with_feature"]["roi"] == 0.0, mo
print("second-half study helpers: de-vig, money columns: OK")
