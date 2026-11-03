import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import tip_sites as ts  # noqa: E402

ROW = """<a href='/x?fixture_id={fid}' id='match-{fid}' class='livescore-match-row' data-status='{st}' data-fid='{fid}'>
<span class='local-time' data-time='{ko}'>18:45</span>
<span class='livescore-team-name'>Home FC</span><span class='livescore-team-name'>Away &amp; Co</span>
<div class='prob-head'>1</div> <div class='prob-val'>50%</div>
<div class='prob-head'>X</div> <div class='prob-val'>30%</div>
<div class='prob-head'>2</div> <div class='prob-val'>20%</div>
<div class='livescore-score-combined' style='x'>2-1</div>
<span class='tip-indicator-circle' style='y'>{tip}</span></a>"""
NOW = datetime(2026, 11, 3, 16, 0, tzinfo=UTC)


def page(*rows):
    return "<div class='livescore-matches-list'>" + "".join(ROW.format(**r) for r in rows) + "</div>"


def test_parse_keeps_only_upcoming_scheduled_tips():
    p = page({"fid": 1, "st": "scheduled", "ko": "2026-11-03T18:45:00+01:00", "tip": "1X"},
             {"fid": 2, "st": "scheduled", "ko": "2026-11-03T15:00:00+01:00", "tip": "1"},     # kicked off
             {"fid": 3, "st": "live", "ko": "2026-11-03T20:00:00+01:00", "tip": "2"},          # not scheduled
             {"fid": 4, "st": "scheduled", "ko": "2026-11-03T21:00:00+01:00", "tip": "2"})
    rows = ts.parse_vitibet(p, NOW)
    assert [r["post_url"] for r in rows] == ["site:vitibet:1", "site:vitibet:4"]
    leg = rows[0]["legs"][0]
    assert (leg["market"], leg["selection"], leg["away"]) == ("dc", "1x", "Away & Co")
    assert leg["kickoff"] == "2026-11-03T17:45:00Z" and leg["p"] == [0.5, 0.3, 0.2] and leg["score_tip"] == [2, 1]
    assert rows[1]["legs"][0]["selection"] == "away"


def test_collect_appends_new_tips_once(tmp_path):
    p = page({"fid": 7, "st": "scheduled", "ko": "2026-11-03T20:00:00+00:00", "tip": "X"})
    assert ts.collect(tmp_path, NOW, get=lambda u: p) == ["vitibet: 1 upcoming tips read, 1 new"]
    assert ts.collect(tmp_path, NOW, get=lambda u: p) == ["vitibet: 1 upcoming tips read, 0 new"]
    lines = (tmp_path / "slips_2026-11-03.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["legs"][0]["selection"] == "draw"


def test_collect_survives_a_site_down(tmp_path):
    def boom(u):
        raise OSError("403")
    assert ts.collect(tmp_path, NOW, get=boom)[0].startswith("vitibet: unavailable")


def test_summary_hit_rate_brier_and_exact_score(tmp_path):
    g = [{"poster": "site:vitibet", "status": "won",
          "legs": [{"market": "1x2", "selection": "home", "p": [0.5, 0.3, 0.2], "score_tip": [2, 1], "score": [2, 1]}]},
         {"poster": "site:vitibet", "status": "lost",
          "legs": [{"market": "1x2", "selection": "home", "p": [0.5, 0.3, 0.2], "score_tip": [1, 0], "score": [0, 0]}]},
         {"poster": "@someone", "status": "won", "legs": [{}]}]
    s = ts.summary(g)["sites"]["vitibet"]
    assert (s["n"], s["won"], s["fav"], s["exact"]) == (2, 1, 1, 1)
    assert abs(s["brier"] / s["nb"] - ((0.25 + 0.09 + 0.04) + (0.25 + 0.49 + 0.04)) / 2) < 1e-9
    out = ts.write_study(tmp_path, g, NOW).read_text(encoding="utf-8")
    assert "| vitibet | 2 | 50% | 0.580 | 50% | 50% |" in out
