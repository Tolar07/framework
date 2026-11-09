"""monitor/acca_singles_paper.py: the Architect's acca (2.5u) + 1u-per-leg singles, graded on paper."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor import acca_singles_paper as asp  # noqa: E402


def _fb_doc(day, acca_result, leg_results, prices=(1.3, 1.4, 1.5)):
    fixtures = [f"T{i} v U{i}" for i in range(len(leg_results))]
    return {
        "date": day,
        "singles": [{"fixture": f, "price": p, "result": r}
                    for f, p, r in zip(fixtures, prices, leg_results, strict=True)],
        "accas": [{"name": "Acca A", "odds": round(1.3 * 1.4 * 1.5, 2), "result": acca_result,
                   "legs": fixtures,
                   "leg_detail": [{"fixture": f, "price": p} for f, p in zip(fixtures, prices, strict=True)]}],
        "btts": [{"name": "BTTS 1", "odds": 1.69, "result": None,
                  "alt_legs": [{"price": 1.3, "result": "won"}, {"price": 1.3, "result": None}]}],
    }


def test_returns_won_slip():
    s = {"odds": 2.73, "result": "won", "legs": [(1.3, "won"), (1.4, "won"), (1.5, "won")]}
    r = asp.returns(s)
    assert abs(r["acca_back"] - 2.5 * 2.73) < 1e-9
    assert abs(r["singles_back"] - (1.3 + 1.4 + 1.5)) < 1e-9
    assert r["acca_staked"] == 2.5 and r["singles_staked"] == 3.0


def test_returns_lost_slip_singles_cushion_and_void():
    s = {"odds": 2.73, "result": "lost", "legs": [(1.3, "won"), (1.4, "lost"), (1.5, "void")]}
    r = asp.returns(s)
    assert r["acca_back"] == 0.0
    assert abs(r["singles_back"] - (1.3 + 1.0)) < 1e-9     # won leg at its price, void = stake back


def test_collect_counts_only_fully_graded_slips():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "picks_2026-11-07.json").write_text(json.dumps(_fb_doc("2026-11-07", "lost", ["won", "lost", "won"])))
        (p / "picks_2026-11-08.json").write_text(json.dumps(_fb_doc("2026-11-08", "won", ["won", "won", "won"])))
        rows = asp.collect(p)
        card = asp.build(rows, "2026-11-09")
    assert card["all"]["slips"] == 2
    assert card["pending"] == 2                     # the two half-graded BTTS slips
    assert card["all"]["acca_won"] == 1
    # combo staked 2 * (2.5 + 3) = 11; back = 2.5*2.73 + (1.3+1.4+1.5) + (1.3+1.5)
    expect = (2.5 * 2.73 + 4.2 + 2.8) / 11 - 1
    assert abs(card["all"]["combo_roi"] - round(expect, 4)) < 1e-4
    assert "ACCA + SINGLES" in card["report_line"]


def test_basketball_leg_results_from_one_leg_slips():
    doc = {
        "date": "2026-11-07",
        "singles": [
            {"legs": ["e1"], "result": "won", "leg_detail": [{"event_id": "e1", "pick": "Over 140.5"}]},
            {"legs": ["e2"], "result": "lost", "leg_detail": [{"event_id": "e2", "pick": "A -3.5"}]},
        ],
        "clv_accas": [{"name": "CLV A", "odds": 3.6, "result": "lost", "legs": ["e1", "e2"],
                       "leg_detail": [{"event_id": "e1", "pick": "Over 140.5", "price": 1.9},
                                      {"event_id": "e2", "pick": "A -3.5", "price": 1.9}]}],
        "accas": [{"name": "Acca X", "odds": 3.6, "result": "lost", "legs": ["e1", "e3"],
                   "leg_detail": [{"event_id": "e1", "pick": "Over 140.5", "price": 1.9},
                                  {"event_id": "e3", "pick": "B ML", "price": 1.9}]}],
    }
    slips = asp.basketball_slips(doc)
    by = {s["name"]: s for s in slips}
    assert by["CLV A"]["graded"] and not by["Acca X"]["graded"]   # e3 has no graded one-leg slip: PENDING
    assert by["CLV A"]["legs"] == [(1.9, "won"), (1.9, "lost")]


def test_no_graded_slips_reads_cleanly():
    card = asp.build([], "2026-11-09")
    assert card["all"]["combo_roi"] is None
    assert "no graded slips yet" in card["report_line"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
