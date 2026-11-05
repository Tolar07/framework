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
            "covered": covered, "sides": {"B:219||Home": home_price, "B:219||Away": 2.30},
            "oids": {"B:219||Home": "4", "B:219||Away": "5"}}


def _book(sels):
    assert sels == [{"eventId": "sr:match:1", "marketId": "219", "specifier": "", "outcomeId": "4"}]
    return "ABC123", None, "1 leg(s)"


def test_picks_value_and_freezes():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        assert wb.update([_row()], [_event()], NOW, folder=d, book=_book) == 1   # 1.62 x ~0.662 = +7%
        doc = json.loads((d / f"wb_{KO:%Y-%m-%d}.json").read_text(encoding="utf-8"))
        p = doc["picks"][0]
        assert p["pick"] == "Real Madrid to win" and p["value"] > 0.03 and p["result"] is None
        # the NBA board's fields, so the bots stake it like an nba_ pick (Architect 2026-11-05)
        assert (p["market_id"], p["specifier"], p["outcome"], p["outcome_id"]) == ("219", "", "Home", "4")
        assert p["code"] == "ABC123" and p["chance"] == p["fair"] and p["tip"] == p["ko"]
        assert wb.update([_row(home_price=1.90)], [_event()], NOW, folder=d, book=_book) == 0   # frozen at entry
        assert json.loads((d / f"wb_{KO:%Y-%m-%d}.json").read_text(encoding="utf-8"))["picks"][0]["price"] == 1.62


def test_skips_nba_far_games_thin_books_and_no_value():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        assert wb.update([_row(covered=True)], [_event()], NOW, folder=d) == 0           # the NBA board's own
        assert wb.update([_row(ko=NOW + timedelta(hours=30))], [_event()], NOW, folder=d) == 0
        assert wb.update([_row()], [_event(liq=3.0)], NOW, folder=d) == 0                  # thin book
        assert wb.update([_row(home_price=1.50)], [_event()], NOW, folder=d) == 0          # below fair


def test_booking_retries_and_skips_started():
    doc = {"picks": [{"ko": KO.strftime("%Y-%m-%dT%H:%M:%SZ"), "code": None, "outcome_id": "4",
                      "event_id": "sr:match:1", "market_id": "219", "specifier": ""},
                     {"ko": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "code": None,
                      "outcome_id": "4", "event_id": "x", "market_id": "219", "specifier": ""}]}
    assert wb.book_codes(doc, NOW, book=lambda s: (None, None, "down")) == 0     # failure stays PENDING
    assert wb.book_codes(doc, NOW, book=_book) == 1 and doc["picks"][0]["code"] == "ABC123"
    assert doc["picks"][1]["code"] is None                                       # started: never booked


def test_describe():
    assert wb.describe("B:223|hcp=-6.5|Home (-6.5)", "A", "B") == "A -6.5"
    assert wb.describe("B:225|total=160.5|Over 160.5", "A", "B") == "Over 160.5 points"
    assert wb.describe("B:68|total=80.5|Under 80.5", "A", "B") == "1st half Under 80.5 points"


def main() -> None:
    test_picks_value_and_freezes()
    test_skips_nba_far_games_thin_books_and_no_value()
    test_booking_retries_and_skips_started()
    test_describe()
    print("world_basketball_test OK")


if __name__ == "__main__":
    main()
