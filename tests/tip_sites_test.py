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
    js = lambda u: ""   # noqa: E731 — statarea: an empty page, no browser in tests
    assert ts.collect(tmp_path, NOW, get=lambda u: p, get_js=js)[0] == "vitibet: 1 upcoming tips read, 1 new"
    assert ts.collect(tmp_path, NOW, get=lambda u: p, get_js=js)[0] == "vitibet: 1 upcoming tips read, 0 new"
    lines = (tmp_path / "slips_2026-11-03.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["legs"][0]["selection"] == "draw"


def test_collect_survives_a_site_down(tmp_path):
    def boom(u):
        raise OSError("403")
    notes = ts.collect(tmp_path, NOW, get=boom, get_js=boom)
    assert notes[0].startswith("vitibet: unavailable") and notes[1].startswith("statarea: unavailable")


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


SA = """<div class="zoneastext">Europe/London</div>
<div class="match" id="{mid}"><div class="tip"><div class="ownheader">TIP</div><div class="value"><div class="type5">{tip}</div></div></div>
<div class="teams"><div class="ownheader">{when}</div>
<div class="hostteam"><div class="goals">{g}</div><div class="name"><a href="x">Atletico Madrid</a></div></div>
<div class="guestteam"><div class="goals">{g}</div><div class="name"><a href="x">Bayern Munich</a></div></div></div>
<div class="coefrow">""" + "".join(f'<div class="coefbox"><div class="value r{v}">{v}</div></div>' for v in (32, 33, 35, 30, 36, 34, 87, 68, 45, 68, 32)) + """
</div><div class="userrow"></div>"""


def test_parse_statarea_upcoming_only_and_time_zone():
    page = (SA.format(mid=1, tip="X2", when="2026-11-03 20:00", g="-")
            + SA.format(mid=2, tip="1", when="2026-11-03 20:00", g="1")         # score showing: started
            + SA.format(mid=3, tip="1", when="2026-11-03 15:00", g="-")         # kicked off before NOW
            + SA.format(mid=4, tip="+2.5", when="2026-11-03 21:00", g="-"))     # a tip we can't grade
    rows = ts.parse_statarea(page, NOW)
    assert [r["post_url"] for r in rows] == ["site:statarea:1"]
    leg = rows[0]["legs"][0]
    assert (leg["market"], leg["selection"], leg["kickoff"]) == ("dc", "x2", "2026-11-03T20:00:00Z")
    assert leg["p"] == [0.32, 0.33, 0.35] and leg["p_over"]["2.5"] == 0.68 and leg["p_btts"] == 0.68
    summer = SA.format(mid=5, tip="1", when="2027-06-01 20:00", g="-")      # BST: 20:00 London = 19:00 UTC
    assert ts.parse_statarea(summer, NOW)[0]["legs"][0]["kickoff"] == "2027-06-01T19:00:00Z"
