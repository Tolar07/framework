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
        assert [x["code"] for x in a["accas"]] == ["ACC1"]                                  # 3 picks: no split
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


def test_night_three_accas():
    """Architect 2026-11-06 17:51: three accas a night: all picks, then the two halves by tip-off."""
    first = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "wb_2026-11-06.json").write_text(json.dumps({"date": "2026-11-06", "picks": [
            _pick(i, first + timedelta(minutes=30 * i)) for i in range(5)]}), encoding="utf-8")
        n = iter(["ALL", "A1", "B1"])
        assert wb.night_accas(first - timedelta(hours=1), d, book=lambda s: next(n)) == ["2026-11-06"]
        a = json.loads((d / "acca_2026-11-06.json").read_text(encoding="utf-8"))
        assert [(x["key"], x["code"], x["codes"]) for x in a["accas"]] == [
            ("all", "ALL", ["C0", "C1", "C2", "C3", "C4"]), ("A", "A1", ["C0", "C1", "C2"]), ("B", "B1", ["C3", "C4"])]
        assert a["code"] == "ALL" and len(a["legs"]) == 5
    with tempfile.TemporaryDirectory() as t:                                                 # one booking fails:
        d = Path(t)                                                                          # none written, retried
        (d / "wb_2026-11-06.json").write_text(json.dumps({"date": "2026-11-06", "picks": [
            _pick(i, first + timedelta(minutes=30 * i)) for i in range(5)]}), encoding="utf-8")
        n = iter(["ALL", None, "B1"])
        assert wb.night_accas(first - timedelta(hours=1), d, book=lambda s: next(n)) == []
        assert not (d / "acca_2026-11-06.json").exists()


def test_one_basketball_set_nba_plus_world():
    """Architect 2026-11-06 18:35: NBA and every other league are one board; the morning NBA board books the
    night's slips (all + 2 halves by tip-off) from NBA + world basketball picks of the NBA night window."""
    start = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    now = datetime(2026, 11, 7, 6, 47, tzinfo=UTC)
    nba = [{**_pick(i, datetime(2026, 11, 8, 0, 30 * i, tzinfo=UTC), code="N"), "event_id": f"sr:match:n{i}"}
           for i in range(2)]
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "wb_2026-11-07.json").write_text(json.dumps({"date": "2026-11-07", "picks": [
            _pick(1, datetime(2026, 11, 7, 18, 0, tzinfo=UTC)),                  # EuroLeague evening: in
            _pick(2, datetime(2026, 11, 7, 23, 0, tzinfo=UTC)),
            _pick(3, datetime(2026, 11, 7, 9, 0, tzinfo=UTC))]}), encoding="utf-8")   # before 10:00 UTC: out
        (d / "wb_2026-11-08.json").write_text(json.dumps({"date": "2026-11-08", "picks": [
            _pick(4, datetime(2026, 11, 8, 11, 0, tzinfo=UTC))]}), encoding="utf-8")  # next night: out
        n = iter(["ALL", "A1", "B1"])
        seen = []
        doc = wb.combined_accas(now, "2026-11-07", start, start + timedelta(hours=24), nba,
                                lambda s: seen.append(s) or next(n), folder=d)
        assert [(a["key"], a["codes"]) for a in doc["accas"]] == [
            ("all", ["C1", "C2", "N0", "N1"]), ("A", ["C1", "C2"]), ("B", ["N0", "N1"])]
        assert json.loads((d / "acca_2026-11-07.json").read_text(encoding="utf-8"))["code"] == "ALL"
        again = wb.combined_accas(now, "2026-11-07", start, start + timedelta(hours=24), nba, lambda s: 1 / 0, folder=d)
        assert again["code"] == "ALL" and len(seen) == 3                       # frozen: never rebooked
        assert wb.night_accas(datetime(2026, 11, 7, 16, 30, tzinfo=UTC), d, book=lambda s: 1 / 0) == []   # no fallback
    with tempfile.TemporaryDirectory() as t:                                   # one leg: nothing booked
        assert wb.combined_accas(now, "2026-11-07", start, start + timedelta(hours=24), nba[:1], lambda s: "X",
                                 folder=Path(t)) is None
    import run_nba
    with tempfile.TemporaryDirectory() as t:
        got = run_nba.basketball_accas(now, start.date(), nba, book_many=lambda s: "K", folder=Path(t))
        assert [a["code"] for a in got] == ["K"]                                # 2 legs: the all-picks slip only


def test_all_halves_slips_on_the_two_test_nights_only():
    """Architect 2026-11-06 19:06: the all + 2 halves slips were a test for tonight and tomorrow, then stop."""
    assert set(wb.TEST_NIGHTS) == {"2026-11-06", "2026-11-07"}
    start = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)
    nba = [{**_pick(i, datetime(2026, 11, 9, 0, 20 * i, tzinfo=UTC)), "event_id": f"n{i}"} for i in range(3)]
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        assert wb.combined_accas(start - timedelta(hours=3), "2026-11-08", start, start + timedelta(hours=24), nba,
                                 lambda s: 1 / 0, folder=d) is None
        (d / "wb_2026-11-08.json").write_text(json.dumps({"date": "2026-11-08", "picks": [
            _pick(i, datetime(2026, 11, 8, 20, i, tzinfo=UTC)) for i in range(3)]}), encoding="utf-8")
        assert wb.night_accas(datetime(2026, 11, 8, 19, 0, tzinfo=UTC), d, book=lambda s: 1 / 0) == []
        assert not list(d.glob("acca_*.json"))


def main() -> None:
    test_picks_value_and_freezes()
    test_skips_nba_far_games_thin_books_and_no_value()
    test_pick_is_bot_ready()
    test_staked_fields_backfill_and_retry()
    test_describe()
    test_night_acca_all_picks_once()
    test_night_three_accas()
    test_one_basketball_set_nba_plus_world()
    test_all_halves_slips_on_the_two_test_nights_only()
    print("world_basketball_test OK")


if __name__ == "__main__":
    main()
