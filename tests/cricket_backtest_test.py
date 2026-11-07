"""Cricket backtest: parser, Elo replay, no-peeking split, report. No network."""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import cricket_backtest as cb  # noqa: E402


def _m(day, a, b, win, result=None):
    out = {"winner": win} if win else {}
    if result:
        out["result"] = result
    return {"info": {"dates": [day], "teams": [a, b], "outcome": out}}


def _zip(matches):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("README.txt", "x")
        for i, m in enumerate(matches):
            z.writestr(f"{i}.json", json.dumps(m))
    return buf.getvalue()


def _matches():
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(1600):
        y = 2010 + i // 100
        a, b = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if a == b:
            b = teams[(i + 2) % 4]
        out.append(_m(f"{y}-{1 + (i % 100) // 10:02d}-{1 + i % 10:02d}", a, b, "A" if "A" in (a, b) else a))
    return out


def _fetch(key):
    return _zip(_matches()) if key == "t20s_male" else b"bad"


def test_parse_skips_no_result_tie_and_bad():
    assert cb.parse_match(_m("2020-01-01", "A", "B", "A"), "T20")["y"] == 1.0
    assert cb.parse_match(_m("2020-01-01", "A", "B", "B"), "T20")["y"] == 0.0
    assert cb.parse_match(_m("2020-01-01", "A", "B", None, "no result"), "T20") is None
    assert cb.parse_match(_m("2020-01-01", "A", "B", "A", "tie"), "T20") is None
    assert cb.parse_match({"x": 1}, "T20") is None


def test_load_orders_and_survives_bad_format():
    g = cb.load(_fetch)
    assert len(g) == 1600
    days = [x["day"] for x in g]
    assert days == sorted(days)


def test_replay_no_lookahead_and_min_games():
    g = cb.load(_fetch)
    p = cb.replay(g, 24.0, 0.0)
    assert p[0] is None
    g2 = [dict(x) for x in g]
    g2[-1]["y"] = 1.0 - g2[-1]["y"]
    assert cb.replay(g2, 24.0, 0.0)[:-1] == p[:-1]


def test_run_report_counts_tries():
    text = cb.run(cb.load(_fetch))
    assert "Settings tried: **6**" in text and "Record only" in text
