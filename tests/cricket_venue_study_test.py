"""Cricket venue study: parser, no-lookahead replay, report. No network."""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import cricket_venue_study as vs  # noqa: E402


def _match(day, venue, runs_per_ball=1, overs=20, balls=None, wickets=0, n_overs=20):
    balls = overs * 6 if balls is None else balls
    dels = []
    for i in range(balls):
        d = {"runs": {"total": runs_per_ball}}
        if i < wickets:
            d["wickets"] = [{"player_out": "x"}]
        dels.append(d)
    ovs = [{"deliveries": dels[i:i + 6]} for i in range(0, len(dels), 6)]
    return {"info": {"dates": [day], "venue": venue, "overs": n_overs}, "innings": [{"overs": ovs}]}


def test_parse_full_short_and_allout():
    assert vs.parse_match(_match("2020-01-01", "V"), "T20", 20)["total"] == 120.0
    assert vs.parse_match(_match("2020-01-01", "V", balls=60), "T20", 20) is None      # shortened: skipped
    assert vs.parse_match(_match("2020-01-01", "V", balls=60, wickets=10), "T20", 20)["total"] == 60.0
    assert vs.parse_match(_match("2020-01-01", None), "T20", 20) is None               # no venue: skipped
    assert vs.parse_match(_match("2020-01-01", "V", n_overs=10), "T20", 20) is None    # wrong format length
    assert vs.parse_match({}, "T20", 20) is None


def test_replay_has_no_lookahead():
    games = [{"fmt": "T20", "venue": "A" if i % 2 else "B", "total": 150.0 + (30 if i % 2 else -30),
              "day": f"2015-01-{1 + i % 28:02d}", "year": 2015} for i in range(200)]
    v1, f1 = vs.replay(games, 5.0, 0.0)
    games2 = [dict(g) for g in games]
    games2[-1]["total"] = 9999.0                      # change only the LAST result
    v2, f2 = vs.replay(games2, 5.0, 0.0)
    assert v1 == v2 and f1 == f2                      # every earlier guess is unchanged
    assert v1[10] is None and f1[10] is None          # format not known yet: PENDING, not invented
    assert v1[-1] > 150 and v1[-2] < 150              # venue A runs high, B low


def _fetch(key):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(1300):
            year = 2010 + i // 90
            day = f"{year}-{1 + (i % 90) // 8:02d}-{1 + i % 8:02d}"
            venue = "High" if i % 2 else "Low"
            m = _match(day, venue, runs_per_ball=2 if i % 2 else 1, overs=20)
            z.writestr(f"{i}.json", json.dumps(m))
    return buf.getvalue()


def test_report_venue_beats_format_and_counts_tries():
    games = vs.load(fetch=lambda k: _fetch(k) if k == "t20s_male" else (_ for _ in ()).throw(OSError("x")))
    assert len(games) == 1300
    text = vs.run(games)
    assert "Settings tried: **8**" in text and "PENDING" in text and "Record only" in text
    assert "VENUE shrunk" in text and "it helps" in text
