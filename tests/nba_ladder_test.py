"""
Offline test of the NBA ladder reader (engine/nba_ladder.py): ladders parsed
from a SportyBet event, and the fit recovering a known centre and spread
from margin-carrying prices — totals and handicaps.
"""
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_ladder as nl

N = NormalDist()


def priced(p: float, margin: float = 0.05) -> tuple[float, float]:
    """Two decimal prices for chance p with a bookmaker margin spread evenly."""
    return round(1 / (p * (1 + margin)), 3), round(1 / ((1 - p) * (1 + margin)), 3)


# a total ladder priced from Normal(224, 16): the fit must find (224, 16)
total_rows = []
for line in [210.5 + i for i in range(0, 28, 2)]:
    o, u = priced(1 - N.cdf((line - 224) / 16))
    total_rows.append([line, o, u])
c, sd, n = nl.fit("225", total_rows)
assert abs(c - 224) < 0.2 and abs(sd - 16) < 0.2 and n == len(total_rows), (c, sd, n)

# a handicap ladder from home margin ~ Normal(4, 16.5): home line h covered when margin > -h
hcp_rows = []
for h in (-12.5, -9.5, -6.5, -3.5, -0.5, 2.5, 5.5, 8.5, -4):
    home, away = priced(1 - N.cdf((-h - 4) / 16.5))
    hcp_rows.append([h, home, away])
c, sd, n = nl.fit("223", hcp_rows)
assert abs(c - 4) < 0.2 and abs(sd - 16.5) < 0.2 and n == 8, (c, sd, n)     # whole line -4 left out
assert nl.fit("225", total_rows[:2]) is None, "fewer than 3 lines: no fit"
print("fit recovers centre and spread (totals, handicaps; margin removed): OK")

ev = {"eventId": "sr:match:1", "markets": [
    {"id": "225", "specifier": "total=220.5", "outcomes": [{"desc": "Over 220.5", "odds": "1.87"}, {"desc": "Under 220.5", "odds": "1.87"}]},
    {"id": "225", "specifier": "total=210.5", "outcomes": [{"desc": "Over 210.5", "odds": "1.40"}, {"desc": "Under 210.5", "odds": "2.80"}]},
    {"id": "303", "specifier": "hcp=-1.5|quarternr=2", "outcomes": [{"desc": "Home (-1.5)", "odds": "1.9"}, {"desc": "Away (+1.5)", "odds": "1.85"}]},
    {"id": "219", "outcomes": [{"desc": "Home", "odds": "1.5"}, {"desc": "Away", "odds": "2.6"}]},
    {"id": "227", "specifier": "total=110.5", "outcomes": [{"desc": "Over 110.5", "odds": "bad"}, {"desc": "Under 110.5", "odds": "1.9"}]}]}
lads = nl.ladders(ev)
assert lads == {"225": [[210.5, 1.4, 2.8], [220.5, 1.87, 1.87]], "303/q2": [[-1.5, 1.9, 1.85]]}, lads
print("ladders parsed per market, quarter keyed, bad prices dropped: OK")

g = NS(id="401", tip="2026-10-21T23:30Z", ml_home=1.5, ml_away=2.6, spread=-4.5, total=221.0)
now = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)
row = nl.snapshot_row(now, "regular", ev, "BOS", "LAL", g)
assert row["at"] == "2026-10-21T18:00:00Z" and row["home"] == "BOS" and row["sharp"]["total"] == 221.0
assert row["fits"]["225"] is None and "303/q2" in row["ladders"]
d = Path(tempfile.mkdtemp())
assert nl.save([row, row], now, d).name == "2026-10-21.jsonl"
assert len(nl.load(d)) == 2 and nl.save([], now, d) is None
print("snapshot rows saved and read back: OK")

print("ALL NBA LADDER TESTS PASSED")
