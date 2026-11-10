"""Baseball total-runs backtest (framework#346): ESPN parse, closing-total median, no-peeking replay, bets.
No network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import baseball_totals_backtest as bt  # noqa: E402


def _event(i, sa=3, sh=5, stype=2, done=True):
    return {"id": str(i), "date": f"2023-06-{1 + i % 28:02d}T23:05Z", "season": {"type": stype, "year": 2023},
            "competitions": [{"status": {"type": {"completed": done}},
                              "competitors": [{"homeAway": "home", "team": {"abbreviation": "NYY"}, "score": str(sh)},
                                              {"homeAway": "away", "team": {"abbreviation": "BOS"}, "score": str(sa)}]}]}


def _item(line, over=-110, under=-110, name="Bet X"):
    return {"provider": {"name": name}, "overUnder": line, "overOdds": over, "underOdds": under}


def test_scores_keep_finished_regular_and_playoff():
    got = bt.scores_of_day({"events": [_event(1), _event(2, stype=1), _event(3, done=False), _event(4, stype=3, sa=1, sh=0)]})
    assert [g["id"] for g in got] == ["1", "4"]
    assert got[0]["total"] == 8 and got[0]["ra"] == 3 and got[0]["rb"] == 5
    assert bt.scores_of_day(None) == []


def test_close_total_median_and_skips():
    odds = {"items": [_item(8.5), _item(9.0), _item(7.0, name="Live Odds"), _item(None), _item(9.5, -110, -3000)]}
    t = bt.close_total(odds)
    assert t["line"] == 8.75 and abs(t["over"] - (1 + 100 / 110)) < 1e-9
    assert bt.close_total({"items": [_item(None)]}) is None and bt.close_total(None) is None


def _games(n=600):
    out = []
    for i in range(n):
        out.append({"key": f"2022-{1 + i // 30:02d}-{1 + i % 30:02d}", "season": 2022 if i < 400 else 2023,
                    "a": "AAA" if i % 2 else "CCC", "b": "BBB", "ra": 4, "rb": 5, "total": 9 if i % 3 else 7,
                    "line": 8.5, "over": 1.9, "under": 1.9})
    return out


def test_expected_total_never_peeks():
    g = _games()
    base = bt.expected_totals(g, 0.98, 10.0, 1.0)
    assert base[0] is None and base[5] is None and base[-1] is not None
    g2 = [dict(x) for x in g]
    g2[-1]["total"] = 30                                   # the result of the last game must not move its own forecast
    assert bt.expected_totals(g2, 0.98, 10.0, 1.0)[-1] == base[-1]


def test_blend_and_evaluate():
    assert bt.blend(10.0, 8.0, 0.5) == 9.0
    g = _games()
    e = bt.expected_totals(g, 0.98, 10.0, 0.0)
    r = bt.evaluate(g, e, (2023, 2023), 1.0)               # weight 1 = the line itself
    assert r["n"] > 0 and abs(r["rmse"] - r["rmse_line"]) < 1e-12


def test_bets_drop_pushes_and_price_correctly():
    g = [{"season": 2023, "total": 9, "line": 8.5, "over": 2.0, "under": 1.8},
         {"season": 2023, "total": 8, "line": 8.0, "over": 2.0, "under": 1.8},      # push: not a bet
         {"season": 2023, "total": 7, "line": 8.5, "over": 2.0, "under": 1.8}]
    b = bt.bets(g, [10.0, 10.0, 10.0], (2023, 2023), 0.0, 0.5)                      # always Over
    assert b["n"] == 2 and abs(b["book"] - (1.0 - 1.0) / 2) < 1e-9
    assert abs(b["fair"] - ((1 - bt.COMMISSION) - 1.0) / 2) < 1e-9
    assert bt.bets(g, [None, None, None], (2023, 2023), 0.0, 0.5)["n"] == 0


def test_run_writes_a_report_with_record_only_line():
    g = _games(900)
    for i, x in enumerate(g):
        x["season"] = 2019 + i // 130
    text = bt.run(g, ["2020: 3 of 9 games without a closing total (skipped)"])
    assert "Record only" in text and "Tries counted" in text and "RMSE" in text
