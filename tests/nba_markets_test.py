"""
Offline test of the NBA every-market record (engine/nba_markets.py), the
market study (backtest/nba_market_study.py) and the board's STUDY LINES
(engine/nba_value.study_lines, run_nba.render). No network.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import nba_market_study as st  # noqa: E402

import run_nba  # noqa: E402
from engine import nba_markets as nm  # noqa: E402
from engine import nba_value as nv  # noqa: E402

# Home 60-58 at half time, 104-104 after four quarters, 112-108 after overtime
qh, qa = [30, 30, 20, 24, 8], [28, 30, 24, 22, 4]
assert nm.settle_any("219", "", "Home", 112, 108, qh, qa) == 1, "winner counts overtime"
assert nm.settle_any("1", "", "Draw", 112, 108, qh, qa) == 1, "1X2 is regulation time: a draw"
assert nm.settle_any("1", "", "Home", 112, 108, qh, qa) == 0
assert nm.settle_any("47", "", "Home/Draw", 112, 108, qh, qa) == 1, "half time Home, full time (regulation) Draw"
assert nm.settle_any("47", "", "Home/Home", 112, 108, qh, qa) == 0
assert nm.settle_any("225", "total=219.5", "Over 219.5", 112, 108, qh, qa) == 1
assert nm.settle_any("999", "", "Over 100.5", 112, 108, qh, qa) is None, "an unknown market is never guessed"
assert nm.settle_any("1", "", "Home", 112, 108, None, None) is None, "no quarter scores: PENDING"
print("settlement of every market: OK")

page = {"markets": [{"id": "1", "desc": "1X2", "specifier": "", "status": 0,
                     "outcomes": [{"desc": "Home", "odds": "2.1"}, {"desc": "Draw", "odds": "15.5"},
                                  {"desc": "Away", "odds": "1.86"}]},
                    {"id": "777", "desc": "2nd half - total 110.5", "specifier": "total=110.5", "status": 2,
                     "outcomes": [{"desc": "Over 110.5", "odds": "1.9"}, {"desc": "Under 110.5", "odds": "x"}]}]}
mk = nm.compact_markets(page)
assert [m["id"] for m in mk] == ["1", "777"] and mk[1]["open"] is False and len(mk[1]["outcomes"]) == 1
looks = [{"event_id": "e1", "at": "2026-10-13T20:00:00Z", "tip": "2026-10-14T00:00Z"},
         {"event_id": "e1", "at": "2026-10-13T23:45:00Z", "tip": "2026-10-14T00:00Z"},
         {"event_id": "e1", "at": "2026-10-14T00:15:00Z", "tip": "2026-10-14T00:00Z"}]
assert nm.last_looks(looks)[0]["at"] == "2026-10-13T23:45:00Z", "the last look BEFORE tip-off"
print("every-market record: OK")

lad = {"event_id": "e2", "stage": "preseason", "at": "2026-10-13T20:00:00Z", "tip": "2026-10-14T00:00Z",
       "ladders": {"225": [[219.5, 1.87, 1.87]], "223": [[-4.5, 1.91, 1.83]]}}
row = st.from_ladder(lad)
g = SimpleNamespace(hs=112, as_=108, q_home=qh, q_away=qa)
settled, unsettled = st.settle_rows([row, {"event_id": "e1", "stage": "preseason", "markets": mk}],
                                    {"e2": g, "e1": g})
got = {(r["family"], r["won"]) for r in settled}
assert ("Total points (incl. OT)", 1) in got and ("Handicap (incl. OT)", 0) in got, got
assert ("1X2 (regulation)", 1) in got, "1X2 settled from the every-market record"
assert "2nd half - total [777]" not in unsettled, "a closed market is left out"
text = st.build([row], {"e2": g})
assert "| Total points (incl. OT) | 2 | 50.0% | 50.0% |" in text and "## Regular" in text, text
assert "NO DATA — PENDING" in st.build([], {}), "no graded game: PENDING"
print("market study: OK")

sharp = SimpleNamespace(ml_home=1.5, ml_away=2.6, spread=-5.5, total=226.5)
event = {"markets": [{"id": "225", "specifier": f"total={t}", "status": 0,
                      "outcomes": [{"desc": f"Over {t}", "odds": str(o), "id": "12"},
                                   {"desc": f"Under {t}", "odds": str(u), "id": "13"}]}
                     for t, o, u in ((222.5, 1.6, 2.25), (226.5, 1.87, 1.87), (230.5, 2.25, 1.6))]}
lines = nv.study_lines(event, sharp)
assert len(lines) == 1 and lines[0]["market_id"] == "225", "one line per market: the closest to value"
assert lines[0]["ev"] == max(r["ev"] for r in (nv.study_lines({"markets": [m]}, sharp)[0] for m in event["markets"]))
board = run_nba.render([], "2026-10-14", "RID", 1, None, [],
                       [{"tip": "2026-10-14T00:00:00+00:00", "stage": "preseason", "home": "Magic",
                         "away": "Cavaliers", "lines": lines}])
assert "STUDY LINES — not picks, nothing booked (order 41)" in board and "Magic v Cavaliers · PRESEASON" in board
assert "No SportyBet NBA price above the fair price today." in board, "study lines never become picks"
print("board study lines: OK")

print("ALL NBA MARKET TESTS PASSED")
