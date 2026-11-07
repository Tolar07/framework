from pathlib import Path
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


def test_calibration_buckets_and_pending():
    games = {f"g{i}": {"sides": {"a": {"won": i % 2 == 0, "first": {"price": 2.0}}}} for i in range(40)}
    games["bad"] = {"sides": {"a": {"won": None, "first": {"price": 2.0}}, "b": {"won": True, "first": {}}}}
    cal = d.calibration([("2026-11-07", {"games": games})])
    b = [c for c in cal if c["lo"] == 0.4][0]
    assert b["n"] == 40 and b["won"] == 20 and b["implied"] == 0.5 and b["actual"] == 0.5
    thin = d.calibration([("x", _doc())])
    assert all(c["actual"] is None for c in thin)
    assert "PENDING (<30)" in d.render(d.summarise([("x", _doc())], None), datetime(2026, 11, 7, tzinfo=UTC))


def test_workflow_runs_darts_studies_on_grade_and_saves_them():
    """#341: the studies read the private board, so they must run in the multisport workflow (not only locally)."""
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "multisport.yml").read_text(encoding="utf-8")
    assert "python backtest/darts_study.py" in wf and "python backtest/darts_format_study.py" in wf
    assert "backtest/DARTS_STUDY.md" in wf


def test_feed_probe_is_in_report_and_unscored():
    from backtest import darts_study as ds
    assert all(scored == 0 for _, _, scored, _ in ds.FEED_PROBE)
    assert "Results-feed probe" in "".join(ds.feed_probe_lines())
