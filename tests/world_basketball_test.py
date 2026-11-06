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


def test_staked_fields_backfill_and_retry():
    """Architect 2026-11-05: staked like NBA. The bots read chance / tip / event_id; a pick frozen
    before the bot fields gets them, and a PENDING code is retried every look."""
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        row = {**_row(), "oids": {"B:219||Home": "4", "B:219||Away": "5"}}
        assert wb.update([row], [_event()], NOW, folder=d, book=lambda s: None) == 1     # booking down
        f = d / f"wb_{KO:%Y-%m-%d}.json"
        p = json.loads(f.read_text(encoding="utf-8"))["picks"][0]
        assert p["code"] is None and p["chance"] == p["fair"] and p["tip"] == p["ko"] and p["event_id"] == "sr:match:1"
        assert wb.update([row], [_event()], NOW, folder=d, book=lambda s: "RETRY1") == 0      # retried, not re-picked
        assert json.loads(f.read_text(encoding="utf-8"))["picks"][0]["code"] == "RETRY1"
        old = json.loads(f.read_text(encoding="utf-8"))
        for k in ("market_id", "specifier", "outcome", "outcome_id", "code", "chance", "tip", "event_id", "venues"):
            old["picks"][0].pop(k, None)                                                  # frozen this morning
        f.write_text(json.dumps(old), encoding="utf-8")
        wb.update([row], [_event()], NOW, folder=d, book=lambda s: "BACK1")
        p = json.loads(f.read_text(encoding="utf-8"))["picks"][0]
        assert (p["market_id"], p["outcome_id"], p["code"], p["chance"]) == ("219", "4", "BACK1", p["fair"])


def test_describe():
    assert wb.describe("B:223|hcp=-6.5|Home (-6.5)", "A", "B") == "A -6.5"
    assert wb.describe("B:225|total=160.5|Over 160.5", "A", "B") == "Over 160.5 points"
    assert wb.describe("B:68|total=80.5|Under 80.5", "A", "B") == "1st half Under 80.5 points"


def _pick(i, tip, code="C", price=1.8, chance=0.6):
    return {"event_id": f"sr:match:{i}", "market_id": "223", "specifier": "hcp=-20.5", "outcome_id": "1715",
            "code": f"{code}{i}", "price": price, "chance": chance, "tip": tip.strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_night_acca_all_picks_once():
    """Architect 2026-11-06: every pick of the night on ONE slip as well as the singles, booked once
    from ACCA_LEAD before the night's first tip-off (12:00-12:00 UTC night), started games left off."""
    n0 = datetime(2026, 11, 6, 19, 0, tzinfo=UTC)
    first = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "wb_2026-11-06.json").write_text(json.dumps({"date": "2026-11-06", "picks": [
            _pick(1, first), _pick(2, first + timedelta(hours=1, minutes=30)),
            _pick(9, datetime(2026, 11, 6, 9, 0, tzinfo=UTC))]}), encoding="utf-8")     # the night before
        (d / "wb_2026-11-07.json").write_text(json.dumps({"date": "2026-11-07", "picks": [
            _pick(3, datetime(2026, 11, 7, 3, 30, tzinfo=UTC)), {**_pick(4, datetime(2026, 11, 7, 2, 0, tzinfo=UTC)),
                                                                  "code": None},       # no code: not on the slip
            _pick(5, datetime(2026, 11, 7, 13, 0, tzinfo=UTC))]}), encoding="utf-8")    # the next night
        seen = []
        book = lambda s: seen.append(s) or "ACC1"                                           # noqa: E731
        assert wb.night_accas(n0, d, book=book) == []                                       # 3 h before: not yet
        assert wb.night_accas(n0 + timedelta(hours=1), d, book=lambda s: None) == []        # booking down: retried
        assert not (d / "acca_2026-11-06.json").exists()
        assert wb.night_accas(n0 + timedelta(hours=1), d, book=book) == ["2026-11-06"]
        a = json.loads((d / "acca_2026-11-06.json").read_text(encoding="utf-8"))
        assert a["code"] == "ACC1" and a["codes"] == ["C1", "C2", "C3"] and a["result"] is None
        assert a["legs"] == ["sr:match:1", "sr:match:2", "sr:match:3"] and a["odds"] == round(1.8 ** 3, 2)
        assert seen[0][0] == {"eventId": "sr:match:1", "marketId": "223", "specifier": "hcp=-20.5",
                              "outcomeId": "1715"}
        assert wb.night_accas(n0 + timedelta(hours=2), d, book=book) == [] and len(seen) == 1   # frozen
        late = datetime(2026, 11, 6, 22, 30, tzinfo=UTC)                                    # first game started
        with tempfile.TemporaryDirectory() as t2:
            d2 = Path(t2)
            for f in d.glob("wb_*.json"):
                (d2 / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            assert wb.night_accas(late, d2, book=book) == ["2026-11-06"]
            assert json.loads((d2 / "acca_2026-11-06.json").read_text(encoding="utf-8"))["codes"] == ["C2", "C3"]
    assert wb.night_of(datetime(2026, 11, 7, 11, 59, tzinfo=UTC)) == "2026-11-06"
    assert wb.night_of(datetime(2026, 11, 7, 12, 0, tzinfo=UTC)) == "2026-11-07"
    import os
    if os.environ.get("GITHUB_ACTIONS") != "true":
        assert wb._book_many([{"eventId": "x"}]) is None                                    # never calls SportyBet here


def main() -> None:
    test_picks_value_and_freezes()
    test_skips_nba_far_games_thin_books_and_no_value()
    test_pick_is_bot_ready()
    test_staked_fields_backfill_and_retry()
    test_describe()
    test_night_acca_all_picks_once()
    print("world_basketball_test OK")


if __name__ == "__main__":
    main()
