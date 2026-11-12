"""
data/espn_sports_history.py + engine/sport_atlas.py + backtest/sport_atlas_study.py. Offline, hand-made rows.
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest"))
from data import espn_sports_history as es  # noqa: E402
from engine import sport_atlas as sa  # noqa: E402
import sport_atlas_study as sas  # noqa: E402

# American odds -> decimal
assert abs(es.american_to_decimal(-110) - 1.909) < 0.001 and es.american_to_decimal(150) == 2.5
assert es.american_to_decimal(50) is None

EV = {"id": "9", "date": "2024-03-15T23:00Z", "season": {"year": 2024}, "status": {"type": {"completed": True}},
      "competitions": [{"competitors": [
          {"homeAway": "home", "score": "96", "team": {"id": "1", "displayName": "H"}, "linescores": [{"value": 26}, {"value": 19}, {"value": 22}, {"value": 29}]},
          {"homeAway": "away", "score": "107", "team": {"id": "2", "displayName": "A"}, "linescores": [{"value": 28}, {"value": 26}, {"value": 38}, {"value": 15}]}]}]}
g = es.parse_game(EV, "nba")
assert g["ft"] == [96, 107] and g["periods"][2] == [22, 38] and g["regulation"] == 4
bad = {**EV, "competitions": [{"competitors": [dict(EV["competitions"][0]["competitors"][0], score="99"), EV["competitions"][0]["competitors"][1]]}]}
assert es.parse_game(bad, "nba")["periods"] is None                       # periods that don't add up are dropped
ODDS = {"items": [
    {"provider": {"name": "Book A"}, "overUnder": 220.0, "overOdds": -110, "underOdds": -110, "spread": 10.5,
     "homeTeamOdds": {"moneyLine": 400, "spreadOdds": -110}, "awayTeamOdds": {"moneyLine": -500, "spreadOdds": -110}},
    {"provider": {"name": "Book B"}, "overUnder": 221.0, "overOdds": -105, "underOdds": -115, "spread": 10.0,
     "homeTeamOdds": {"moneyLine": 420, "spreadOdds": -112}, "awayTeamOdds": {"moneyLine": -550, "spreadOdds": -108}},
    {"provider": {"name": "Book A - Live Odds"}, "overUnder": 250.0}]}
pr = es.parse_odds(ODDS)
assert pr["total"] == 220.5 and pr["spread"] == 10.25 and abs(pr["ml_home"] - 5.1) < 1e-9   # live line left out

with tempfile.TemporaryDirectory() as d:
    def get(url):
        return ODDS if "odds" in url else {"events": [EV]}
    out = es.run("nba", date(2024, 3, 15), date(2024, 3, 16), Path(d), get=get, workers=2)
    assert "1 new games" in out, out
    rows = es.load(Path(d))
    assert len(rows) == 1 and rows[0]["prices"]["total"] == 220.5

# ESPN saying stop (403 / 429): the run ends politely and the dates stay to read
with tempfile.TemporaryDirectory() as d:
    def blocked(url):
        raise es.Blocked("403")
    out = es.run("nba", date(2024, 3, 15), date(2024, 3, 16), Path(d), get=blocked)
    assert "ESPN said stop" in out and "2 dates still to read" in out, out

# markets
m = {**g, "prices": pr}
M = sa.SPORT_MARKETS["basketball"]
assert M["over the posted total"](m) == 0.0                 # 203 < 220.5
assert M["home covers the spread"](m) == 0.0                # 96 + 10.25 < 107
assert M["1st half home win"](m) == 0.0 and M["1st quarter home win"](m) == 0.0 and M["overtime"](m) == 0.0
assert sa.PRICED["home win"](m) == (pr["ml_home"], pr["ml_away"])
H = sa.SPORT_MARKETS["hockey"]
hk = {"ft": [3, 2], "periods": [[1, 1], [1, 1], [0, 0], [1, 0]], "regulation": 3, "prices": None}
assert H["overtime / shoot-out"](hk) == 1.0 and H["1st period both score"](hk) == 1.0 and H["over the posted total"](hk) is None

# SportyBet main line = the line with the closest two prices
assert sa._main_line({"total|160.5|over": 1.5, "total|160.5|under": 2.4, "total|165.5|over": 1.88, "total|165.5|under": 1.9},
                     "total", "over", "under")[1] == 165.5

# PriceTrend: a team that keeps covering builds a signal; the away side's record counts against the yes side
pt = sa.PriceTrend()
row = lambda i, h, a: {"hk": h, "ak": a, "sk": "2024", "date": f"2024-01-{i:02d}"}
for i in range(1, 6):
    pt.see("home covers the spread", row(i, "X", f"o{i}"), 1.0, 0.5)    # X covers at home 5 times
    pt.see("home covers the spread", row(i, f"p{i}", "Y"), 1.0, 0.5)    # Y fails to cover away 5 times
s = pt.signal("home covers the spread", row(9, "X", "Y"))
assert abs(s - 0.5) < 1e-9, s

# trend rules: chosen early, judged late
bets = [{"ko": f"2024-01-{d:02d}", "market": "home win", "s": 0.2, "yes": 2.0, "no": 2.0, "y": 1.0} for d in range(1, 29)]
r = [x for x in sas.trend_rules(bets, "2024-01-15") if x["side"] == "yes" and x["gap"] == 0.10][0]
assert r["disc_n"] == 14 and r["hold_n"] == 14 and abs(r["hold_roi"] - 1.0) < 1e-9
assert sas.verdict(r) == "TOO FEW"
print("sport_atlas_test OK")
