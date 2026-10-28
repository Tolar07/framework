"""
Offline test of the NBA projection study (backtest/nba_projection_study.py, Architect
2026-10-28 step 4): loading recorded projections against graded games, the error table,
both-sides Brier / log loss, CLV against the sharp close, the side record, line-up-shock
games apart, and the report.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import nba_projection_study as S

graded = [{"g": "1", "tip": "2026-10-29T23:30Z", "line": 222.5, "spread": -4.5, "hs": 120, "as": 110, "h1": 112, "q1": 57},
          {"g": "2", "tip": "2026-10-29T23:30Z", "line": 230.5, "spread": 2.5, "hs": 100, "as": 105, "h1": 104, "q1": 50}]


def rec(gid, total, spread, over, home, shock):
    return {"espn_id": gid, "home": "BOS", "away": "NYK",
            "projection": {"total": total, "spread": spread, "h1_total": total * 0.5, "q1_total": total * 0.25},
            "sides": {"total": {"sportybet": {"projection": {"line": 220.5, "over": over, "under": 1 - over},
                                              "sharp": {"line": 220.5, "over": 0.5, "under": 0.5}}},
                      "spread": {"sharp": {"projection": {"line": -4.5, "home": home, "away": 1 - home},
                                           "sharp": {"line": -4.5, "home": 0.5, "away": 0.5}}}},
            "lineup_shock": {"flag": True, "out": ["Star"]} if shock else None}


doc = {"study": [{"espn_id": "1", "sharp": {"total": 220.5, "spread": -4.5}, "sb_main": {"225": 220.5}},
                 {"espn_id": "2", "sharp": {"total": 230.5, "spread": 2.5}, "sb_main": {"225": 231.5}}],
       "players": {"projections": [rec("1", 226.0, -6.0, 0.62, 0.58, False), rec("2", 224.0, 1.0, 0.40, 0.45, True),
                                   {"espn_id": "3", "projection": None, "why": ["stale"]}]}}

with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    (t / "nba_2026-10-30.json").write_text(json.dumps(doc))
    (t / "nba_watch_2026-10-30.json").write_text("{}")
    g = t / "graded.jsonl"
    g.write_text("".join(json.dumps(r) + "\n" for r in graded))
    recs = S.load(t, g)
assert [r["espn_id"] for r in recs] == ["1", "2"] and recs[0]["board"] == "2026-10-30"
assert recs[1]["sb_main"] == {"225": 231.5} and recs[0]["board_sharp"]["total"] == 220.5
print("load: OK")

e = S.errors(recs)
assert e["total"]["projection"]["n"] == 2 and e["total"]["projection"]["mae"] == (4 + 19) / 2
assert e["total"]["sharp close"]["mae"] == (7.5 + 25.5) / 2 and e["total"]["SportyBet"]["n"] == 2
assert e["spread"]["projection"]["mae"] == (4 + 4) / 2, e["spread"]["projection"]     # actual -10 / +5
assert e["spread"]["sharp close"]["bias"] == ((-4.5 + 10) + (2.5 - 5)) / 2
print("errors: OK")

r = S.results(recs)
# game 1: total 230 > 220.5 (Over won), home won by 10 > 4.5 (home covered); game 2: 205 Under, home lost
want_b = ((0.62 - 1) ** 2 + (0.58 - 1) ** 2 + 0.40 ** 2 + 0.45 ** 2) / 4
assert r["projection"]["n"] == 4 and abs(r["projection"]["brier"] - want_b) < 1e-9
assert abs(r["sharp"]["brier"] - 0.25) < 1e-9 and r["projection"]["brier"] < r["sharp"]["brier"]
print("results, both sides: OK")

c = S.clv(recs)
# game 1: projection 226 > SportyBet 220.5 -> Over; close 222.5: +2.0. Game 2: 224 < 231.5 -> Under; close 230.5: +1.0
assert c["n"] == 2 and c["mean_pts"] == 1.5 and c["positive"] == 1.0 and c["n_split"] == 2
s = S.side_record(recs)
assert s == {"won": 2, "lost": 0}, s          # 226 vs 220.5 (Over, 230) and 224 vs 230.5 (Under, 205)
print("CLV + side record: OK")

text = S.render(recs, {"n": 0, "mae_projection": None, "mae_sharp_close": None, "won": 0, "lost": 0}, "2026-10-31")
assert "Graded games with a board-time projection: **2** (line-up shock: 1)" in text
assert text.count("### 1. Error") == 2 and "NOT a forecast" in text and "| total | projection | 2 |" in text
print("report: OK")

print("nba_projection_study_test: ALL OK")
