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

# 2026-11-05: every market with a rule. Quarter totals read the quarter named (Q4 = 24 + 22).
assert nm.settle_any("236", "total=45.5|quarternr=4", "Over 45.5", 112, 108, qh, qa) == 1
assert nm.settle_any("236", "total=45.5|quarternr=3", "Over 45.5", 112, 108, qh, qa) == 0, "Q3 = 20 + 24"
assert nm.settle_any("236", "total=57.5|quarternr=1", "Over 57.5", 112, 108, qh, qa) == 1, "Q1 = 30 + 28"
assert nm.settle_any("90", "total=89.5", "Over 89.5", 112, 108, qh, qa) is None, "2nd half: overtime game -> PENDING"
reg_h, reg_a = qh[:4], qa[:4]
assert nm.settle_any("90", "total=89.5", "Over 89.5", 104, 104, reg_h, reg_a) == 1, "2nd half = Q3 + Q4"
assert nm.settle_any("88", "hcp=-1.5", "Home (-1.5)", 104, 104, reg_h, reg_a) == 0, "2nd half 44-46"
assert nm.settle_any("303", "hcp=-1.5|quarternr=4", "Home (-1.5)", 104, 104, reg_h, reg_a) == 1, "Q4 24-22"
assert nm.settle_any("69", "total=59.5", "Over 59.5", 112, 108, qh, qa) == 1, "home 1st half 60"
assert nm.settle_any("757", "total=23.5|quarternr=3", "Under 23.5", 112, 108, qh, qa) == 0, "away Q3 24"
assert nm.settle_any("83", "", "Away", 112, 108, qh, qa) is None, "2nd half 1X2 in an overtime game"
assert nm.settle_any("64", "", "Home", 112, 108, qh, qa) == 1, "1st half draw no bet 60-58"
assert nm.settle_any("302", "quarternr=2", "Home", 112, 108, qh, qa) is None, "Q2 30-30: draw no bet voids"
assert nm.settle_any("220", "", "Yes", 112, 108, qh, qa) == 1, "there was overtime"
assert nm.settle_any("229", "", "Even", 112, 108, qh, qa) == 1, "220 points"
assert nm.settle_any("304", "quarternr=1", "Even", 112, 108, qh, qa) == 1, "Q1 58 points"
print("period markets: OK")

blob = {"boxscore": {"players": [
    {"team": {"abbreviation": "MIL"}, "statistics": [{"keys": [
        "minutes", "points", "fieldGoalsMade-fieldGoalsAttempted",
        "threePointFieldGoalsMade-threePointFieldGoalsAttempted", "rebounds", "assists"], "athletes": [
        {"athlete": {"displayName": "Giannis Antetokounmpo"}, "stats": ["41", "27", "8-20", "0-2", "14", "6"]},
        {"athlete": {"displayName": "Kris Dunn"}, "didNotPlay": True, "stats": []}]}]},
    {"team": {"abbreviation": "LAC"}, "statistics": [{"keys": [
        "minutes", "points", "fieldGoalsMade-fieldGoalsAttempted",
        "threePointFieldGoalsMade-threePointFieldGoalsAttempted", "rebounds", "assists"], "athletes": [
        {"athlete": {"displayName": "Klay Thompson Jr."}, "stats": ["30", "18", "6-14", "4-9", "3", "2"]}]}]}]}}
box = nm.box_stats(blob, "MIL", "LAC")
assert box["players"]["giannis antetokounmpo"]["reb"] == 14 and box["home"]["2pm"] == 8 and box["away"]["3pm"] == 4
assert nm.settle_any("921", "total=25.5|player=sr:player:1", "Over 25.5", 112, 108, qh, qa,
                     name="Antetokounmpo, Giannis total points (incl. overtime)", box=box) == 1
assert nm.settle_any("923", "total=2.5|player=sr:player:2", "Under 2.5", 112, 108, qh, qa,
                     name="Thompson, Klay total rebounds (incl. overtime)", box=box) == 0, "Jr. dropped in matching"
assert nm.settle_any("921", "total=7.5", "Over 7.5", 112, 108, qh, qa,
                     name="Dunn, Kris total points (incl. overtime)", box=box) is None, "did not play: void"
assert nm.settle_any("772", "", "Antetokounmpo, Giannis 14+", 112, 108, qh, qa, box=box) == 1
assert nm.settle_any("772", "", "Antetokounmpo, Giannis 15+", 112, 108, qh, qa, box=box) == 0
assert nm.settle_any("900967", "total=3.5", "Over 3.5", 112, 108, qh, qa, box=box) == 1, "3-pointers 0 + 4"
assert nm.settle_any("900874", "", "Home", 112, 108, qh, qa, box=box) == 1, "assists 6 v 2"
assert nm.settle_any("921", "total=25.5", "Over 25.5", 112, 108, qh, qa, name="X, Y total points", box=None) is None
print("player props and team stat totals: OK")

# every market live (Architect 2026-11-05 evening): the former SHADOW markets are always priced
sh = SimpleNamespace(ml_home=1.5, ml_away=2.6, spread=-5.5, total=226.5)
for mid, spec, desc in (("236", "total=56.5|quarternr=2", "Over 56.5"), ("90", "total=111.5", "Under 111.5"),
                        ("88", "hcp=-2.5", "Home (-2.5)"), ("69", "total=58.5", "Over 58.5"),
                        ("303", "hcp=-0.5|quarternr=4", "Home (-0.5)")):
    assert nv.fair_chance(mid, spec, desc, sh) == nv.fair_chance(mid, spec, desc, sh, shadow=True)
    assert 0.3 < nv.fair_chance(mid, spec, desc, sh) < 0.7
    assert mid in nv.MARKETS
# the blend with SportyBet's own price, and the board text for every new market
assert nv.sb_fair([("Over 56.5", 1.8), ("Under 56.5", 2.0)], "Over 56.5") == (1 / 1.8) / (1 / 1.8 + 1 / 2.0)
assert nv.sb_fair([("Over 56.5", 1.8)], "Over 56.5") is None, "one price: no margin to remove"
_keep = nv.BLEND
nv.BLEND = {"team period points": 0.5}
assert abs(nv.blended(0.70, "69", "total=58.5", 0.50) - 0.60) < 1e-12
assert nv.blended(0.70, "68", "total=110.5", 0.50) == 0.70, "no weight for the group: model only"
assert nv.blended(0.70, "69", "total=58.5", None) == 0.70, "no SportyBet twin: model only"
nv.BLEND = _keep
for mid, spec, desc, text in (("236", "total=56.5|quarternr=3", "Over 56.5", "3rd quarter Over 56.5 points"),
                              ("303", "hcp=-0.5|quarternr=4", "Home (-0.5)", "LAC (-0.5) 4th quarter handicap"),
                              ("90", "total=111.5", "Under 111.5", "2nd half Under 111.5 points (regulation)"),
                              ("88", "hcp=2.5", "Away (-2.5)", "MIA (-2.5) 2nd half handicap"),
                              ("70", "total=58.5", "Under 58.5", "MIA 1st half Under 58.5 points"),
                              ("756", "total=27.5|quarternr=2", "Over 27.5", "LAC 2nd quarter Over 27.5 points")):
    got = nv.display({"market_id": mid, "specifier": spec, "outcome": desc}, "LAC", "MIA")
    assert got == text, (got, text)
assert nv.fair_chance("236", "total=56.5|quarternr=1", "Over 56.5", sh) == \
    nv.fair_chance("236", "total=56.5|quarternr=1", "Over 56.5", sh, shadow=True), "Q1 unchanged"
assert nv.fair_chance("90", "total=111", "Over 111", sh, shadow=True) is None, "whole line can push"
print("shadow pricing: OK")
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
