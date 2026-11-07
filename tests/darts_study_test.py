from datetime import UTC, datetime

from backtest import darts_study as d


def _doc():
    return {"picks": [{"result": "won", "pnl": 0.9, "clv_fair": 0.02}, {"result": "lost", "pnl": -1.0}],
            "games": {"g": {"sides": {"a:ml:x": {"won": True, "first": {"price": 2.0}},
                                       "a:ml:y": {"won": False, "first": {"price": 2.0}}}}}}


def test_empty_is_pending():
    s = d.summarise([], None)
    assert s["verdict"].startswith("PENDING")
    assert "PENDING" in d.render(s, datetime(2026, 11, 7, tzinfo=UTC))


def test_counts_and_brier_verdict():
    elo = {"ratings": {"a": 1500}, "seen": ["x"], "games": {}, "brier": [20.0, 200]}
    s = d.summarise([("2026-11-07", _doc())], elo)
    assert s["sb"]["picks"] == 2 and s["sb"]["won"] == 1
    assert "beats a coin flip" in s["verdict"]
    elo["brier"] = [60.0, 200]
    assert "does NOT" in d.summarise([], elo)["verdict"]
