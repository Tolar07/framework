"""monitor/goals_experiment.py: BTTS / Over-Under 2.5 experiment block, record-only."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor import goals_experiment as ge  # noqa: E402


def _row(ft, btts_raw=0.7, over_raw=0.7):
    return {"fixture": "A v B", "ft": ft, "p": [0.4, 0.3, 0.3, 0.8, over_raw, 0.2, btts_raw]}


def test_game_rows_skip_ungraded_and_read_scores():
    doc = {"rated": [_row("2-1"), _row(None), _row("no-90min-result"), _row("0-0")]}
    rows = ge.game_rows(doc)
    assert len(rows) == 2
    assert rows[0]["btts"] and rows[0]["over"]
    assert not rows[1]["btts"] and not rows[1]["over"]


def test_bars_count_sides_correctly():
    rows = ge.game_rows({"rated": [_row("2-1"), _row("0-0"), _row("1-0", 0.2, 0.2)]})
    assert ge._hit(rows, "btts_yes", 0.5) == (1, 2)      # two high BTTS calls, one landed
    assert ge._hit(rows, "btts_no", 0.55) == (1, 1)      # the 0.2 game: 1-0 is a BTTS no
    assert ge._hit(rows, "under", 0.55) == (1, 1)


def test_slips_and_block_and_pending():
    doc = {"date": "2026-11-05", "rated": [_row("2-2")],
           "btts": [{"result": "won"}, {"result": "lost"}, {"result": None}], "under25": []}
    with tempfile.TemporaryDirectory() as d:
        Path(d, "picks_2026-11-05.json").write_text(json.dumps(doc), encoding="utf-8")
        card = ge.run("2026-11-05", Path(d), write=False)
        assert card["today"]["slips"]["btts"] == {"won": 1, "lost": 1, "open": 1}
        assert "GOALS EXPERIMENT" in card["report_line"] and "BTTS yes 50%+" in card["report_line"]
        empty = ge.run("2026-11-05", Path(d) / "none", write=False)
        assert "no graded games yet" in empty["report_line"]
