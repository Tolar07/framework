"""engine/world_basketball.py — the paper board for every non-NBA basketball league."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import world_basketball as wb  # noqa: E402

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=10)


def _event(back_home=1.50, lay_home=1.52, liq=200.0):
    def r(name, back, lay):
        return {"name": name, "status": "open", "prices": [{"side": "back", "odds": back, "available-amount": liq},
                                                            {"side": "lay", "odds": lay, "available-amount": liq}]}
    return {"id": 9, "name": "Real Madrid vs Olympiacos", "start": KO.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "_sport": "basketball", "markets": [
                {"name": "Moneyline", "market-type": "money_line", "status": "open",
                 "runners": [r("Real Madrid", back_home, lay_home), r("Olympiacos", 2.9, 3.0)]}]}


def _row(home_price=1.62, covered=False, ko=KO):
    return {"sport": "basketball", "id": "sr:match:1", "home": "Real Madrid", "away": "Olympiacos",
            "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "comp": "Euroleague", "country": "International",
            "covered": covered, "sides": {"B:219||Home": home_price, "B:219||Away": 2.30}}


def test_picks_value_and_freezes():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        assert wb.update([_row()], [_event()], NOW, folder=d) == 1          # 1.62 x ~0.662 = +7%
        doc = json.loads((d / f"wb_{KO:%Y-%m-%d}.json").read_text(encoding="utf-8"))
        p = doc["picks"][0]
        assert p["pick"] == "Real Madrid to win" and p["value"] > 0.03 and p["result"] is None
        assert wb.update([_row(home_price=1.90)], [_event()], NOW, folder=d) == 0   # frozen at entry
        assert json.loads((d / f"wb_{KO:%Y-%m-%d}.json").read_text(encoding="utf-8"))["picks"][0]["price"] == 1.62


def test_skips_nba_far_games_thin_books_and_no_value():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        assert wb.update([_row(covered=True)], [_event()], NOW, folder=d) == 0           # the NBA board's own
        assert wb.update([_row(ko=NOW + timedelta(hours=30))], [_event()], NOW, folder=d) == 0
        assert wb.update([_row()], [_event(liq=3.0)], NOW, folder=d) == 0                  # thin book
        assert wb.update([_row(home_price=1.50)], [_event()], NOW, folder=d) == 0          # below fair


def test_pick_is_bot_ready():
    """2026-11-05: each pick carries what a bot needs to place it: SportyBet's market / outcome
    ids, a booking code (PENDING when booking fails or outside Actions) and the venues."""
    booked = []
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        row = {**_row(), "oids": {"B:219||Home": "4", "B:219||Away": "5"}}
        assert wb.update([row], [_event()], NOW, folder=d, book=lambda s: booked.append(s) or "ABC123") == 1
        p = json.loads((d / f"wb_{KO:%Y-%m-%d}.json").read_text(encoding="utf-8"))["picks"][0]
        assert booked == [{"eventId": "sr:match:1", "marketId": "219", "specifier": "", "outcomeId": "4"}]
        assert p["code"] == "ABC123" and p["outcome_id"] == "4" and p["market_id"] == "219"
        assert p["venues"] == {"sportybet": True, "matchbook": True, "betfair_market": True}
    with tempfile.TemporaryDirectory() as t:        # no outcome id: no booking, code PENDING
        assert wb.update([_row()], [_event()], NOW, folder=Path(t), book=lambda s: 1 / 0) == 1
    assert wb.venues("B:68|total=80.5|Over 80.5", True) == {"sportybet": True, "matchbook": True,
                                                            "betfair_market": False}
    assert wb.venues("B:225|total=160.5|Over 160.5", False)["matchbook"] is False   # game not on Matchbook
    import os
    if os.environ.get("GITHUB_ACTIONS") != "true":
        assert wb._book({"eventId": "x"}) is None                                   # never calls SportyBet here


def test_describe():
    assert wb.describe("B:223|hcp=-6.5|Home (-6.5)", "A", "B") == "A -6.5"
    assert wb.describe("B:225|total=160.5|Over 160.5", "A", "B") == "Over 160.5 points"
    assert wb.describe("B:68|total=80.5|Under 80.5", "A", "B") == "1st half Under 80.5 points"


def main() -> None:
    test_picks_value_and_freezes()
    test_skips_nba_far_games_thin_books_and_no_value()
    test_pick_is_bot_ready()
    test_describe()
    print("world_basketball_test OK")


if __name__ == "__main__":
    main()
