"""
Offline tests for the SportyBet booking bridge (pipeline.sportybet_booking):
outcome resolution from a feed-shaped event, the HR35 no-fabrication contract
(unresolved -> None, partial acca -> None), and payload correctness — all with
the network share call monkeypatched, so this never touches SportyBet.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import markets as mkt
from pipeline import sportybet_booking as sbk

# A feed-shaped event (same field names pcUpcomingEvents returns).
EVENT = {
    "eventId": "sr:match:111", "homeTeamName": "Rakow", "awayTeamName": "Legia",
    "markets": [
        {"id": "1", "desc": "1X2", "specifier": None,
         "outcomes": [{"id": "1", "desc": "Home"}, {"id": "2", "desc": "Draw"},
                      {"id": "3", "desc": "Away"}]},
        {"id": "18", "desc": "Over/Under", "specifier": "total=2.5",
         "outcomes": [{"id": "12", "desc": "Over 2.5"}, {"id": "13", "desc": "Under 2.5"}]},
    ],
}

# --- resolve_selection reads real ids from the feed, per market key ---
home = sbk.resolve_selection(EVENT, mkt.HOME)
assert home == {"eventId": "sr:match:111", "marketId": "1", "specifier": "",
                "outcomeId": "1"}, home
under = sbk.resolve_selection(EVENT, mkt.UNDER_25)
assert under["marketId"] == "18" and under["specifier"] == "total=2.5" and under["outcomeId"] == "13"
draw = sbk.resolve_selection(EVENT, mkt.DRAW)
assert draw["outcomeId"] == "2"
# a market the event doesn't carry -> None (never a guessed id)
noev = dict(EVENT, markets=[EVENT["markets"][0]])  # 1X2 only, no O/U
assert sbk.resolve_selection(noev, mkt.UNDER_25) is None
print("resolve_selection: real ids per market, None when absent: OK")

# --- create_booking_code / code_for_legs with the network call stubbed ---
calls = {}
def fake_create(selections):
    calls["last"] = selections
    return "ABC123", "http://www.sportybet.com/ng/?shareCode=ABC123", f"{len(selections)} leg(s)"

sbk.create_booking_code = fake_create  # monkeypatch — no network
index = {("Ekstraklasa", "Rakow", "Legia"): EVENT}

code, url = sbk.code_for_legs(index, [("Ekstraklasa", "Rakow", "Legia", mkt.HOME)])
assert code == "ABC123" and url.endswith("ABC123")
assert calls["last"] == [{"eventId": "sr:match:111", "marketId": "1",
                          "specifier": "", "outcomeId": "1"}]
print("code_for_legs: builds the right payload and returns the code: OK")

# HR35: an unresolvable leg makes the WHOLE code None (never a partial slip)
code2, _ = sbk.code_for_legs(index, [("Ekstraklasa", "Rakow", "Legia", mkt.HOME),
                                     ("Ekstraklasa", "No", "Such", mkt.HOME)])
assert code2 is None, "a leg that can't resolve must void the whole code"
# no index -> None
assert sbk.code_for_legs(None, [("x", "y", "z", mkt.HOME)]) == (None, None)
print("code_for_legs: partial/absent -> None (HR35 no partial slips): OK")

print("\n✅ ALL SPORTYBET BOOKING TESTS PASSED")
