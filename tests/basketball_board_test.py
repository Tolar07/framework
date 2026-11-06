"""engine/basketball_board.py - basketball's own football-style board (Architect 2026-11-06 19:06, #403)."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import basketball_board as bb  # noqa: E402

START = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 7, 6, 47, tzinfo=UTC)


def _p(i: int, tip: datetime, chance: float = 0.58, price: float = 1.8, **kw) -> dict:
    return {"event_id": f"sr:match:{i}", "market_id": "223", "specifier": "hcp=-5.5", "outcome_id": "1714",
            "code": f"C{i}", "price": price, "chance": chance, "home": f"H{i}", "away": f"A{i}",
            "pick": f"H{i} -5.5", "tip": tip.strftime("%Y-%m-%dT%H:%M:%SZ"), **kw}


def test_legs_one_window_one_slip_kind():
    """NBA + world picks of the NBA night only, not started, bookable, one per game."""
    nba = [_p(1, datetime(2026, 11, 8, 0, 0, tzinfo=UTC)), _p(2, datetime(2026, 11, 8, 0, 30, tzinfo=UTC))]
    wb = [{"picks": [_p(3, datetime(2026, 11, 7, 18, 0, tzinfo=UTC)),              # EuroLeague evening: in
                     _p(1, datetime(2026, 11, 8, 0, 0, tzinfo=UTC)),               # same game: NBA's kept
                     _p(4, datetime(2026, 11, 7, 9, 0, tzinfo=UTC)),               # before the night: out
                     {**_p(5, datetime(2026, 11, 7, 20, 0, tzinfo=UTC)), "code": None}]}]   # no code: out
    legs = bb.legs_for(NOW, START, START + timedelta(hours=24), nba, wb)
    assert [x["event_id"] for x in legs] == ["sr:match:3", "sr:match:1", "sr:match:2"]
    assert legs[1]["league"] == "NBA"
    w = bb.windows(legs)
    assert [[x["event_id"] for x in g] for g in w] == [["sr:match:3"], ["sr:match:1", "sr:match:2"]]


def test_sections_like_football():
    """Inside one window: 50+ (3 strongest 60%+), then one CLV acca (4 best value), then 2-leg accas; a match
    in one of them at most. Megas: every pick of the window. Value singles at 10%+."""
    t0 = datetime(2026, 11, 8, 0, 0, tzinfo=UTC)
    chances = [0.66, 0.64, 0.62, 0.55, 0.56, 0.57, 0.54, 0.55, 0.58, 0.53]
    legs = bb.legs_for(NOW, START, START + timedelta(hours=24),
                       [_p(i, t0 + timedelta(minutes=5 * i), chance=c, ev=round(c * 1.8 - 1, 4))
                        for i, c in enumerate(chances)], [])
    b = bb.build(legs)
    assert [len(s["legs"]) for s in b["safe3"]] == [3] and b["safe3"][0]["codes"] == ["C0", "C1", "C2"]
    assert [len(s["legs"]) for s in b["clv_accas"]] == [4]
    assert b["clv_accas"][0]["codes"] == ["C8", "C5", "C4", "C3"]                  # best value of the rest
    assert [s["codes"] for s in b["accas"]] == [["C7", "C6"]]                       # 1 leg left: a single
    used = [c for sec in ("safe3", "clv_accas", "accas") for s in b[sec] for c in s["codes"]]
    assert len(used) == len(set(used))                                             # a match in one acca at most
    assert [len(s["legs"]) for s in b["megas"]] == [10]
    assert len(b["singles"]) == 10 and b["alts"] == []
    assert [s["codes"][0] for s in b["value"]] == ["C0", "C1", "C2"]               # 1.8 x 0.62 - 1 = 11.6%+
    assert all(s["spread_minutes"] <= 90 for sec in bb.SLIP_SECTIONS for s in b[sec])


def test_windows_never_mix_evening_and_midnight():
    eve = [_p(i, datetime(2026, 11, 7, 18, 0, tzinfo=UTC) + timedelta(minutes=10 * i)) for i in range(3)]
    night = [_p(10 + i, datetime(2026, 11, 8, 0, 30, tzinfo=UTC) + timedelta(minutes=10 * i)) for i in range(3)]
    b = bb.build(bb.legs_for(NOW, START, START + timedelta(hours=24), eve + night, []))
    for sec in bb.SLIP_SECTIONS:
        for s in b[sec]:
            assert len({c[:2] == "C1" and len(c) == 3 for c in s["codes"]}) == 1, (sec, s["codes"])
    assert len(b["megas"]) == 2


def test_make_books_freezes_and_renders():
    t0 = datetime(2026, 11, 8, 0, 0, tzinfo=UTC)
    nba = [_p(i, t0 + timedelta(minutes=10 * i), chance=0.62) for i in range(6)]
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        n = iter(f"K{i}" for i in range(50))
        seen = []
        doc = bb.make(NOW, "2026-11-07", START, START + timedelta(hours=24), nba, [],
                      lambda s: seen.append(s) or next(n), folder=d)
        assert doc["all_booked"] and doc["safe3"][0]["code"].startswith("K") and doc["singles"][0]["code"] == "C0"
        assert seen[0][0] == {"eventId": "sr:match:0", "marketId": "223", "specifier": "hcp=-5.5",
                              "outcomeId": "1714"}
        again = bb.make(NOW, "2026-11-07", START, START + timedelta(hours=24), nba, [], lambda s: 1 / 0, folder=d)
        assert again == json.loads((d / "basketball_2026-11-07.json").read_text(encoding="utf-8"))   # frozen
        text = "\n".join(bb.render(doc))
        assert "BASKETBALL BOARD 2026-11-07" in text and doc["safe3"][0]["code"] in text
        assert [s["name"] for s in bb.slips(doc)][0].startswith("Basketball 50+")
    with tempfile.TemporaryDirectory() as t:                                        # booking down: PENDING
        doc = bb.make(NOW, "2026-11-07", START, START + timedelta(hours=24), nba, [], lambda s: None,
                      folder=Path(t))
        assert not doc["all_booked"] and doc["safe3"][0]["code"] is None
    with tempfile.TemporaryDirectory() as t:
        assert bb.make(NOW, "2026-11-07", START, START + timedelta(hours=24), nba[:1], [], lambda s: "X",
                       folder=Path(t)) is None


def test_run_nba_builds_the_board():
    import run_nba
    t0 = datetime(2026, 11, 8, 0, 0, tzinfo=UTC)
    nba = [_p(i, t0 + timedelta(minutes=10 * i), chance=0.62) for i in range(3)]
    with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as w:
        doc = run_nba.basketball_board(NOW, START.date(), nba, book_many=lambda s: "B1", folder=Path(t),
                                       wb_folder=Path(w))
        assert doc["safe3"][0]["code"] == "B1"
        assert run_nba._board_slips(doc)[0] == {"name": "Basketball 50+ #1", "code": "B1",
                                                "legs": ["sr:match:0", "sr:match:1", "sr:match:2"],
                                                "odds": round(1.8 ** 3, 2)}
    assert run_nba._board_slips(None) == []


def test_mega_never_repeats_an_acca():
    """A window of 2 legs makes one 2-leg acca; its mega would be the same slip, so there is none."""
    t0 = datetime(2026, 11, 7, 22, 0, tzinfo=UTC)
    b = bb.build(bb.legs_for(NOW, START, START + timedelta(hours=24), [_p(1, t0), _p(2, t0 + timedelta(minutes=30))], []))
    assert [s["codes"] for s in b["accas"]] == [["C1", "C2"]] and b["megas"] == []


def main() -> None:
    test_legs_one_window_one_slip_kind()
    test_sections_like_football()
    test_windows_never_mix_evening_and_midnight()
    test_make_books_freezes_and_renders()
    test_run_nba_builds_the_board()
    test_mega_never_repeats_an_acca()
    print("basketball_board_test OK")


if __name__ == "__main__":
    main()
