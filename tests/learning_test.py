"""
Offline test of automatic learning from results (improvement #6): market
families, the minimum-sample rule, the shrunk correction, the cap, and the
heartbeat summary. No network.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import learning as lr

# Market families group equivalent keys from both key styles.
assert lr.family("SB:16|hcp=-1|Home") == "Asian handicap"
assert lr.family("SB:10||Home or Draw") == lr.family("DC_1X") == "Double chance"
assert lr.family("SB:1||Home") == lr.family("1X2_HOME") == "1X2"
assert lr.family("OVER_1_5") == lr.family("SB:18|total=2.5|Over") == "Over/Under"
print("families: OK")


def ledger(d, rows, day="2026-10-03"):
    singles = [{"market": m, "league": lg, "chance": c, "price": 1.5, "result": r}
               for m, lg, c, r in rows]
    (Path(d) / f"picks_{day}.json").write_text(
        json.dumps({"date": day, "singles": singles}), encoding="utf-8")


with tempfile.TemporaryDirectory() as d:
    # Fewer than MIN_N results: no correction, summary says so.
    ledger(d, [("DC_1X", "La Liga", 0.7, "lost")] * (lr.MIN_N - 1))
    m = lr.learn(Path(d), today="2026-10-05")
    assert lr.shift(m, "DC_X2", "Serie A") == 0.0
    assert "corrections start" in lr.summary(m)
print("minimum sample: OK")

with tempfile.TemporaryDirectory() as d:
    # Handicaps called at 70% won 6/20 -> cut; Double chance at 60% won 18/20 -> lift.
    rows = ([("SB:16|hcp=-1|Home", "Serie A", 0.70, "won")] * 6 +
            [("SB:16|hcp=-1|Home", "Serie A", 0.70, "lost")] * 14 +
            [("DC_1X", "La Liga", 0.60, "won")] * 18 +
            [("DC_1X", "La Liga", 0.60, "lost")] * 2 +
            [("DC_X2", "La Liga", 0.60, "void")] * 5)          # voids ignored
    # One match day only: no correction yet, however lopsided (MIN_DAYS).
    ledger(d, rows)
    m1 = lr.learn(Path(d), today="2026-10-05")
    assert m1["family"]["Double chance"]["shift"] == 0.0 and m1["family"]["Double chance"]["days"] == 1
    assert lr.shift(m1, "DC_1X", "La Liga") == 0.0, "one day must not move the board"
    # The same results spread over MIN_DAYS match days count.
    for i in range(lr.MIN_DAYS):
        ledger(d, rows[i::lr.MIN_DAYS], day=f"2026-10-0{i + 1}")
    m = lr.learn(Path(d), today="2026-10-05")
    hc = m["family"]["Asian handicap"]
    assert hc["n"] == 20 and hc["wins"] == 6
    assert abs(hc["shift"] - (6 - 14) / (20 + lr.SHRINK)) < 1e-4, hc
    assert m["family"]["Double chance"]["n"] == 20, "voids are not results"
    s_hc = lr.shift(m, "SB:16|hcp=0|Away", "Serie A")
    s_dc = lr.shift(m, "SB:10||Draw or Away", "La Liga")
    assert s_hc < 0 < s_dc, (s_hc, s_dc)
    assert -lr.MAX_SHIFT <= s_hc and s_dc <= lr.MAX_SHIFT, "shift is capped"
    assert lr.shift(m, "OVER_1_5", "Bundesliga") == 0.0, "unseen segment unchanged"
    text = lr.summary(m)
    assert "Asian handicap" in text and "Double chance" in text, text
    # Old results outside the window are forgotten.
    m_late = lr.learn(Path(d), today="2027-03-01")
    assert m_late["family"] == {}
print("learned shifts + cap + window: OK")

print("\n✅ ALL LEARNING TESTS PASSED")
