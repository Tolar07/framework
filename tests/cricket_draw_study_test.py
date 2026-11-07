"""Cricket Test draw study: parser, no-lookahead Elo, report. No network."""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import cricket_draw_study as ds  # noqa: E402


def _m(day, a, b, win=None, result=None):
    out = {"winner": win} if win else {}
    if result:
        out["result"] = result
    return {"info": {"dates": [day], "teams": [a, b], "outcome": out}}


def _fetch(_key):
    teams = ["A", "B", "C", "D"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(1200):
            a, b = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
            if a == b:
                b = teams[(i + 2) % 4]
            day = f"{2010 + i // 75}-{1 + (i % 75) // 7:02d}-{1 + i % 7:02d}"
            m = _m(day, a, b, result="draw") if i % 4 == 0 else _m(day, a, b, "A" if "A" in (a, b) else a)
            z.writestr(f"{i}.json", json.dumps(m))
    return buf.getvalue()


def test_parse_draw_tie_and_bad():
    assert ds.parse_test(_m("2020-01-01", "A", "B", "A"))["res"] == "A"
    assert ds.parse_test(_m("2020-01-01", "A", "B", "B"))["res"] == "B"
    assert ds.parse_test(_m("2020-01-01", "A", "B", result="draw"))["res"] == "D"
    assert ds.parse_test(_m("2020-01-01", "A", "B", result="no result")) is None
    assert ds.parse_test({"x": 1}) is None


def test_probs_sum_to_one_and_load_survives_bad_zip():
    assert abs(sum(ds.probs({"e": 0.7}, 0.25)) - 1) < 1e-12
    assert ds.load(lambda k: b"bad") == []


def test_replay_no_lookahead():
    g = ds.load(_fetch)
    ds.replay(g)
    before = [x["e"] for x in g[:-1]]
    g[-1]["res"] = "B" if g[-1]["res"] != "B" else "A"
    ds.replay(g)
    assert [x["e"] for x in g[:-1]] == before


def test_run_report_counts_rules():
    text = ds.run(ds.load(_fetch))
    assert "Rules tried: **3**" in text and "Record only" in text
