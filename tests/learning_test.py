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

def spread(d, rows, days):
    """The same rows spread over `days` match days."""
    for i in range(days):
        ledger(d, rows[i::days], day=f"2026-09-{10 + i:02d}")


with tempfile.TemporaryDirectory() as d:
    # Handicaps called at 70% won 18/60 -> cut; Double chance at 60% won 54/60 -> lift.
    rows = ([("SB:16|hcp=-1|Home", "Serie A", 0.70, "won")] * 18 +
            [("SB:16|hcp=-1|Home", "Serie A", 0.70, "lost")] * 42 +
            [("DC_1X", "La Liga", 0.60, "won")] * 54 +
            [("DC_1X", "La Liga", 0.60, "lost")] * 6 +
            [("DC_X2", "La Liga", 0.60, "void")] * 5)          # voids ignored
    # One match day only: no correction yet, however lopsided (MIN_DAYS).
    ledger(d, rows)
    m1 = lr.learn(Path(d), today="2026-10-05")
    assert m1["family"]["Double chance"]["shift"] == 0.0 and m1["family"]["Double chance"]["days"] == 1
    assert lr.shift(m1, "DC_1X", "La Liga") == 0.0, "one day must not move the board"
    (Path(d) / "picks_2026-10-03.json").unlink()
    spread(d, rows, lr.MIN_DAYS)
    m = lr.learn(Path(d), today="2026-10-05")
    hc = m["family"]["Asian handicap"]
    assert hc["n"] == 60 and hc["wins"] == 18 and hc["z"] <= -lr.Z_MIN
    assert abs(hc["shift"] - (18 - 42) / (60 + lr.SHRINK)) < 1e-4, hc
    assert m["family"]["Double chance"]["n"] == 60, "voids are not results"
    s_hc = lr.shift(m, "SB:16|hcp=0|Away", "Serie A")
    s_dc = lr.shift(m, "SB:10||Draw or Away", "La Liga")
    assert s_hc < 0 < s_dc, (s_hc, s_dc)
    assert -lr.MAX_SHIFT <= s_hc and s_dc <= lr.MAX_SHIFT, "shift is capped"
    # No double counting: Serie A's picks are all handicaps, so once the family
    # correction is applied the league has nothing left to correct.
    assert abs(m["league"]["Serie A"]["shift"]) < abs(hc["shift"]) / 2, m["league"]["Serie A"]
    assert lr.shift(m, "OVER_1_5", "Bundesliga") == 0.0, "unseen segment unchanged"
    text = lr.summary(m)
    assert "Asian handicap" in text and "Double chance" in text, text
    # Old results outside the window are forgotten.
    m_late = lr.learn(Path(d), today="2027-03-01")
    assert m_late["family"] == {}

with tempfile.TemporaryDirectory() as d:
    # A small, noisy gap never moves anything: 60 picks at 70%, 45 won (exp 42).
    spread(d, [("DC_1X", "La Liga", 0.70, "won")] * 45 +
              [("DC_1X", "La Liga", 0.70, "lost")] * 15, lr.MIN_DAYS)
    m = lr.learn(Path(d), today="2026-10-05")
    assert abs(m["family"]["Double chance"]["z"]) < lr.Z_MIN
    assert lr.shift(m, "DC_1X", "La Liga") == 0.0, "noise below 2 sd must not move the board"

with tempfile.TemporaryDirectory() as d:
    # Learning reads chance_raw (before any learned shift) when it is recorded.
    singles = [{"market": "DC_1X", "league": "La Liga", "chance": 0.80, "chance_raw": 0.60,
                "price": 1.5, "result": r} for r in ["won"] * 30 + ["lost"] * 30]
    for i in range(lr.MIN_DAYS):
        (Path(d) / f"picks_2026-09-{10 + i:02d}.json").write_text(json.dumps(
            {"date": f"2026-09-{10 + i:02d}", "singles": singles[i::lr.MIN_DAYS]}),
            encoding="utf-8")
    m = lr.learn(Path(d), today="2026-10-05")
    assert m["family"]["Double chance"]["expected"] == 36.0, m["family"]["Double chance"]
print("learned shifts + cap + window: OK")

print("\n✅ ALL LEARNING TESTS PASSED")
