"""
Offline test of the 10pm code freeze (engine/freeze.py): a later run keeps the
frozen codes; only slips with a drifted / news-hit / dropped leg get a new
code; a started match is never touched; the message says what changed.
"""
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import freeze

def single(fx, mk, price, code, ko="2026-10-05T18:00:00Z"):
    h, a = fx.split(" v ")
    return {"fixture": fx, "league": "L", "home": h, "away": a, "market": mk,
            "pick": f"{fx} {mk}", "price": price, "code": code, "kickoff": "2026-10-05",
            "kickoff_utc": ko}

led = {"singles": [single("A v B", "DC_1X", 1.30, "S1"), single("C v D", "OVER_1_5", 1.25, "S2"),
                   single("E v F", "DC_X2", 1.28, "S3", ko="2026-10-05T10:00:00Z")],
       "accas": [{"name": "Acca A", "code": "AC1", "legs": ["A v B", "C v D", "E v F"]},
                 {"name": "Acca B", "code": "AC2", "legs": ["C v D", "E v F"]}],
       "safe3": [], "megas": [], "alts": []}
with tempfile.TemporaryDirectory() as d:
    freeze.save("2026-10-05", led, "FROZEN BOARD TEXT", "OLPXDV-20261004-2047-abcdef",
                board_code="MEGA1", board_dir=Path(d))
    fz = freeze.load("2026-10-05", Path(d))
    assert freeze.board_text("2026-10-05", Path(d)) == "FROZEN BOARD TEXT"

def bf(fx, key, news=None, note=""):
    h, a = fx.split(" v ")
    return NS(fixture=f"{fx} (L)", probs=NS(home_team=h, away_team=a), best_market_key=key,
              best_price=1.27, on_deploy_shortlist=True, news_level=news, news_note=note)

board = [bf("A v B", "DC_1X"), bf("C v D", "OVER_1_5"), bf("E v F", "DC_X2")]
now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
booked = []
book = lambda legs: (booked.append(legs) or f"NEW{len(booked)}")

# Nothing moved -> no change, message says so.
lines, recs = freeze.check(fz, board, lambda leg: leg["price"], book, now)
assert lines == [] and recs == [] and "No changes" in freeze.message(fz, lines, "2026-10-05", "R")
print("no change -> keep the frozen codes: OK")

# A v B drifts 1.30 -> 1.40 (+7.7%): its single, Acca A and the board mega change; Acca B doesn't.
board2 = [bf("A v B", "SB:1||Home"), bf("C v D", "OVER_1_5"), bf("E v F", "DC_X2")]
price = lambda leg: 1.40 if leg["fixture"] == "A v B" else leg["price"]
lines, recs = freeze.check(fz, board2, price, book, now, display=lambda k, h, a: f"{h} {k}")
changed = {r["name"] for r in recs}
assert changed == {"A v B", "Acca A", "Board MEGA"}, changed
assert all(r["new_code"] for r in recs) and "AC2" not in " ".join(lines)
assert any("REPLACED by NEW" in l and "Acca A AC1" in l for l in lines), lines
print("drifted leg -> only the slips carrying it get a new code: OK")

# A started match (E v F kicked off at 10:00) is never touched, even if it 'drifts'.
price2 = lambda leg: 9.99 if leg["fixture"] == "E v F" else leg["price"]
lines, recs = freeze.check(fz, board, price2, book, now)
assert recs == [], "started match must not be replaced"
print("started match untouched: OK")

# Team news on C v D with no alternative on the board -> dropped; Acca B (2 legs) -> 1 leg -> withdrawn.
import engine.team_news as _tn
_orig = _tn.assess
_tn.assess = lambda market, news, *a: ({"level": "RISK", "note": "C missing 40%"} if news == "N-CD"
                                       else {"level": "OK", "note": ""})
board3 = [bf("A v B", "DC_1X"), bf("C v D", "OVER_1_5"), bf("E v F", "DC_X2")]
board3[1].team_news = "N-CD"
board3[0].team_news = "N-AB"   # news elsewhere that doesn't touch the frozen pick
lines, recs = freeze.check(fz, board3, lambda leg: leg["price"], book, now)
r_b = next(r for r in recs if r["name"] == "Acca B")
assert r_b["new_code"] is None and any("WITHDRAWN" in l for l in lines)
assert not any(r["name"] == "A v B" for r in recs), "news not touching the frozen pick: no change"
_tn.assess = _orig
print("news-hit leg with no alternative -> dropped / slip withdrawn: OK")

# Scan failure (6 Oct 2026: SportyBet refused the runner, 0 fixtures priced):
# nothing is withdrawn, every leg stays as frozen and the message says which
# matches were not re-checked.
unchecked = []
lines, recs = freeze.check(fz, [], lambda leg: None, book, now, unchecked=unchecked)
assert lines == [] and recs == [], (lines, recs)
assert unchecked == ["A v B", "C v D"], unchecked          # E v F already started
msg = freeze.message(fz, lines, "2026-10-05", "R", unchecked=unchecked)
assert "Not re-checked this run" in msg and "2 match(es)" in msg and "No changes" in msg, msg
print("empty scan -> codes kept, not re-checked matches listed: OK")

# Its league WAS priced but the fixture is gone (postponed) -> still 'left the board'.
board4 = [bf("C v D", "OVER_1_5"), bf("E v F", "DC_X2")]
unchecked = []
lines, recs = freeze.check(fz, board4, lambda leg: leg["price"], book, now, unchecked=unchecked)
assert unchecked == [] and any("no longer on the board" in l for l in lines), lines
print("fixture gone from a priced league -> still replaced: OK")

print("\n✅ ALL FREEZE TESTS PASSED")

# Order 38 on a frozen board: an FA Cup underdog handicap frozen before the rule
# existed is replaced by the board's current pick; a favourite's line is kept.
dog = "SB:16|hcp=-1.5|Away (+1.5)"
fav = "SB:16|hcp=-1.5|Home (-1.5)"
led4 = {"singles": [dict(single("G v H", dog, 1.23, "S4"), league="FA Cup"),
                    dict(single("I v J", fav, 1.25, "S5"), league="FA Cup")],
        "accas": [], "safe3": [], "megas": [], "alts": []}
with tempfile.TemporaryDirectory() as d:
    freeze.save("2026-10-06", led4, "T", "R", board_dir=Path(d))
    fz4 = freeze.load("2026-10-06", Path(d))
board4 = [NS(**{**vars(bf("G v H", "SB:18|total=1.5|Over 1.5")), "fixture": "G v H (FA Cup)"}),
          NS(**{**vars(bf("I v J", fav)), "fixture": "I v J (FA Cup)"})]
lines, recs = freeze.check(fz4, board4, lambda leg: leg["price"], book, now)
assert [r["name"] for r in recs] == ["G v H"], recs
assert "order 38" in recs[0]["notes"][0] and recs[0]["alt_legs"][0]["market"] == "SB:18|total=1.5|Over 1.5"
assert freeze.forbidden(dog, "League Two") is None and freeze.forbidden(fav, "FA Cup") is None
print("FA Cup underdog handicap on a frozen board -> replaced (order 38): OK")
