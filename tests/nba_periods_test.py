"""
Offline test of the NBA period markets (backtest/NBA_PERIOD_STUDY.md):
team totals (227/228), regulation total (18), 1st-half (66) and quarter
(303) handicaps — fair chance from the sharp line, whole lines never priced,
settlement from quarter scores, display and the draft bet365 lines.
"""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_teams as nt
from engine import nba_value as nv

sharp = NS(ml_home=1.5405, ml_away=2.54, spread=-6.0, total=220.0)   # home 113, away 107

# team totals: centred on (T -/+ S) / 2 plus the measured bias
p = nv.fair_chance("227", "total=113.5", "Over 113.5", sharp)
assert abs(p - (1 - nv._phi((113.5 - 113.18) / nv.TEAM_SD))) < 1e-9 and 0.48 < p < 0.50, p
assert abs(nv.fair_chance("228", "total=101.5", "Over 101.5", sharp) - (1 - nv._phi((101.5 - 107.01) / nv.TEAM_SD))) < 1e-9
assert abs(p + nv.fair_chance("227", "total=113.5", "Under 113.5", sharp) - 1) < 1e-9
assert nv.fair_chance("227", "total=113", "Over 113", sharp) is None, "a whole line can push"
assert nv.fair_chance("227", "total=113.5", "Over 113.5", NS(**{**vars(sharp), "spread": None})) is None
print("team totals: OK")

# regulation total: one point under the sharp total (no overtime), sd 17.2
p = nv.fair_chance("18", "total=219.5", "Over 219.5", sharp)
assert abs(p - (1 - nv._phi((219.5 - 219.0) / nv.REG_SD))) < 1e-9
print("regulation total: OK")

# 1st-half handicap: home margin ~ Normal(0.639 x 6, 11.0)
p = nv.fair_chance("66", "hcp=-3.5", "Home (-3.5)", sharp)
assert abs(p - (1 - nv._phi((3.5 - 0.639 * 6) / 11.0))) < 1e-9
assert abs(p + nv.fair_chance("66", "hcp=-3.5", "Away (+3.5)", sharp) - 1) < 1e-9
assert nv.fair_chance("66", "hcp=-3", "Home (-3)", sharp) is None
# quarter handicaps: quarters 1-3 only
p1 = nv.fair_chance("303", "hcp=-1.5|quarternr=1", "Home (-1.5)", sharp)
assert abs(p1 - (1 - nv._phi((1.5 - 0.331 * 6) / 8.3))) < 1e-9
assert nv.fair_chance("303", "hcp=-1.5|quarternr=4", "Home (-1.5)", sharp) is None, "Q4: OT rule unconfirmed"
assert nv.fair_chance("303", "hcp=-1.5", "Home (-1.5)", sharp) is None
print("1st-half and quarter handicaps: OK")

# candidates now scan the new markets
ev = {"markets": [
    {"id": "219", "outcomes": [{"id": "4", "desc": "Home", "odds": "1.55"}, {"id": "5", "desc": "Away", "odds": "2.45"}]},
    {"id": "228", "specifier": "total=95.5", "outcomes": [{"id": "12", "desc": "Over 95.5", "odds": "1.30"},
                                                         {"id": "13", "desc": "Under 95.5", "odds": "3.2"}]}]}
picks, suspect = nv.candidates(ev, sharp)
assert [r["outcome"] for r in picks] == ["Over 95.5"], picks          # ~84% at 1.30 = +9%
print("candidates include the new markets: OK")

# a CLOSED SportyBet line (status 2: listed with a stale price, not bettable) is never picked
closed = {"markets": [{**ev["markets"][1], "status": 2}]}
assert nv.candidates(closed, sharp) == ([], []), "closed lines never become picks (2026-10-07)"
assert nv.candidates({"markets": [{**ev["markets"][1], "status": 0}]}, sharp)[0], "open lines still do"
assert nv.sportybet_winner_chance({"markets": [{**ev["markets"][0], "status": 1}]}) is None
print("closed / suspended SportyBet lines never picked: OK")

# settlement: final score incl. OT for team totals; quarters for the rest
qh, qa = [30, 28, 25, 27, 10], [25, 26, 30, 29, 8]      # 120-118 after OT (110-110 in regulation)
assert nv.settle({"market_id": "227", "outcome": "Over 119.5", "specifier": "total=119.5"}, 120, 118) == "won"
assert nv.settle({"market_id": "228", "outcome": "Under 117.5", "specifier": "total=117.5"}, 120, 118) == "lost"
assert nv.settle({"market_id": "18", "outcome": "Under 220.5", "specifier": "total=220.5"}, 120, 118, qh, qa) == "won"
assert nv.settle({"market_id": "18", "outcome": "Under 220.5", "specifier": "total=220.5"}, 120, 118) is None
assert nv.settle({"market_id": "66", "outcome": "Home (-6.5)", "specifier": "hcp=-6.5"}, 120, 118, qh, qa) == "won"   # 58-51
assert nv.settle({"market_id": "303", "outcome": "Away (+2.5)", "specifier": "hcp=-2.5|quarternr=2"},
                 120, 118, qh, qa) == "won"                                                      # Q2 28-26
assert nv.settle({"market_id": "303", "outcome": "Home (-4.5)", "specifier": "hcp=-4.5|quarternr=3"},
                 120, 118, qh, qa) == "lost"                                                     # Q3 25-30
print("settlement (team totals incl. OT; regulation, halves, quarters from quarter scores): OK")

assert nv.display({"market_id": "227", "outcome": "Over 112.5"}, "Boston Celtics", "LA Lakers") == \
    "Boston Celtics Over 112.5 points (incl. OT)"
assert nv.display({"market_id": "18", "outcome": "Under 220.5"}, "B", "L") == "Under 220.5 points (regulation time, no OT)"
assert nv.display({"market_id": "303", "outcome": "Away (+2.5)", "specifier": "hcp=-2.5|quarternr=2"},
                  "Boston Celtics", "LA Lakers") == "LA Lakers (+2.5) 2nd quarter handicap"
bos, lal = nt.BY_KEY["BOS"], nt.BY_KEY["LAL"]
assert nt.bet365_pick({"market_id": "227", "outcome": "Over 112.5"}, bos, lal) == "Team Totals: BOS Celtics Over 112.5"
assert nt.bet365_pick({"market_id": "66", "outcome": "Away (+3.5)"}, bos, lal) == "1st Half › Spread: LA Lakers +3.5"
assert nt.bet365_pick({"market_id": "303", "outcome": "Home (-1.5)", "specifier": "hcp=-1.5|quarternr=2"},
                      bos, lal) == "2nd Quarter › Spread: BOS Celtics -1.5"
assert nt.bet365_pick({"market_id": "18", "outcome": "Over 220.5"}, bos, lal) is None, "bet365 totals include OT"
print("display + draft bet365 lines: OK")

print("ALL NBA PERIOD-MARKET TESTS PASSED")
