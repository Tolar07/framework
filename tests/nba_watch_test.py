"""
Offline test of the NBA line watch (monitor/nba_watch.py): a line move is
measured against the first line seen, value is re-checked against the
current sharp line, one pick per game (board or watch), a LAG is reported
once and never picked, alerts render, and nothing touches git outside
GitHub Actions.
"""
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_teams as nt
from monitor import nba_watch as w

now = datetime(2026, 10, 21, 21, 0, tzinfo=UTC)
tip = datetime(2026, 10, 21, 23, 30, tzinfo=UTC)
bos, lal = nt.BY_KEY["BOS"], nt.BY_KEY["LAL"]


def event(eid, home_p=1.85, away_p=1.95, total_line=231.5, over=1.95, under=1.85):
    return {"eventId": eid, "homeTeamName": "Boston Celtics", "awayTeamName": "Los Angeles Lakers",
            "markets": [
                {"id": "219", "outcomes": [{"id": "4", "desc": "Home", "odds": str(home_p)},
                                           {"id": "5", "desc": "Away", "odds": str(away_p)}]},
                {"id": "225", "specifier": f"total={total_line}",
                 "outcomes": [{"id": "12", "desc": f"Over {total_line}", "odds": str(over)},
                              {"id": "13", "desc": f"Under {total_line}", "odds": str(under)}]}]}


def game(total, spread=-1.5, ml=(1.87, 1.95)):
    return NS(id="401", tip="2026-10-21T23:30Z", ml_home=ml[0], ml_away=ml[1], spread=spread, total=total)


# round 1: sharp total 231.5 = SportyBet's line -> no value; first line recorded
state, taken = {}, set()
picks, lags, snaps = w.check(now, [("regular", event("e1"), tip, bos, lal, game(231.5))], state, taken)
assert picks == [] and lags == [] and len(snaps) == 1
assert state["first"]["e1"]["total"] == 231.5
print("first look records the line, no value at a fair price: OK")

# round 2: star ruled out, sharp total drops to 224.5; SportyBet still 231.5 -> Under has value
later = now.replace(hour=22)
picks, lags, _ = w.check(later, [("regular", event("e1"), tip, bos, lal, game(224.5))], state, taken)
assert len(picks) == 1 and picks[0]["outcome"] == "Under 231.5" and picks[0]["source"] == "watch", picks
assert "total 231.5 → 224.5" in picks[0]["reason"] and picks[0]["ev"] >= 0.05
assert picks[0]["bet365"]["pick"] == "Game Lines › Total: Under 231.5" and "e1" in taken
print("line move found, SportyBet's stale price alerted as a paper pick: OK")

# round 3: same game again -> no second pick (one per game)
picks, _, _ = w.check(later, [("regular", event("e1"), tip, bos, lal, game(224.5))], state, taken)
assert picks == []
# a game already on the evening board is never re-picked by the watch
picks, _, _ = w.check(later, [("regular", event("e2"), tip, bos, lal, game(224.5))], {}, {"e2"})
assert picks == []
print("one pick per game, board picks respected: OK")

# a spread move with SportyBet's winner price left far behind -> LAG once, no pick
st = {"first": {"e3": {"at": "21:00Z", "spread": -1.5, "total": 231.5, "ml_home": 1.87, "ml_away": 1.95}}}
gone = game(231.5, spread=-9.5, ml=(1.25, 4.2))
picks, lags, _ = w.check(later, [("regular", event("e3"), tip, bos, lal, gone)], st, set())
assert picks == [] and len(lags) == 1 and "spread -1.5 → -9.5" in lags[0] and "check by hand" in lags[0]
_, lags, _ = w.check(later, [("regular", event("e3"), tip, bos, lal, gone)], st, set())
assert lags == [], "a LAG is reported once"
print("LAG reported once, never picked: OK")

# alert text
txt = w.render(later, "OLPXDV-20261021-2200-abc123",
               [{**p, "code": "ABC123"} for p in w.check(later, [("regular", event("e9"), tip, bos, lal,
                                                                   game(224.5))], {"first": {"e9": state["first"]["e1"]}}, set())[0]],
               ["X v Y: check by hand"])
assert "Run ID: OLPXDV-20261021-2200-abc123" in txt and "Under 231.5" in txt and "why: sharp line moved" in txt
assert "bet365: Game Lines › Total: Under 231.5" in txt and "LAG — check by hand" in txt and "paper" in txt
print("alert text: OK")

# loop helpers: rounds on :00/:15/:30/:45; never touches git outside GitHub Actions
assert w.next_round(datetime(2026, 10, 21, 21, 7, 30, tzinfo=UTC)).minute == 15
assert w.next_round(datetime(2026, 10, 21, 21, 45, 0, tzinfo=UTC)).minute == 0
os.environ.pop("GITHUB_ACTIONS", None)
assert not w.in_actions() and w.persist(now) == "not saved (outside GitHub Actions)"
assert w.lagos_date(datetime(2026, 10, 21, 23, 30, tzinfo=UTC)) == "2026-10-22"
print("loop helpers, no git outside Actions: OK")

# order 41: NBA alerts go to the Architect's own chat only, never the subscribers
src = (Path(__file__).parent.parent / "monitor" / "nba_watch.py").read_text(encoding="utf-8")
assert "notify.send_telegram(text, chat_id=owner)" in src and "send_everyone" not in src and "deliver(" not in src
print("alerts to the Architect's chat only: OK")

print("ALL NBA LINE-WATCH TESTS PASSED")
