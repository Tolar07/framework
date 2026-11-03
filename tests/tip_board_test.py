import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import tip_board as tb  # noqa: E402


def slip(site, fid, home, away, ko, sel, p, market="1x2"):
    return {"poster": f"site:{site}", "post_url": f"site:{site}:{fid}",
            "legs": [{"home": home, "away": away, "kickoff": ko, "market": market, "selection": sel, "p": p}]}


SLIPS = [slip("vitibet", 1, "Arsenal", "Chelsea", "2026-11-03T20:00:00Z", "home", [0.5, 0.3, 0.2]),
         slip("statarea", 9, "Arsenal FC", "Chelsea", "2026-11-03T20:00:00Z", "1x", [0.55, 0.25, 0.2], "dc"),
         slip("vitibet", 2, "Leeds", "Hull", "2026-11-03T19:45:00Z", "away", [0.3, 0.3, 0.4]),
         slip("statarea", 8, "Leeds United", "Hull City", "2026-11-03T19:45:00Z", "home", [0.5, 0.3, 0.2]),
         slip("vitibet", 3, "Ajax", "PSV", "2026-11-04T19:00:00Z", "home", [0.5, 0.3, 0.2])]
VIEWS = [{"home": "Arsenal", "away": "Chelsea", "p": [0.6, 0.25, 0.15]}]


def test_board_groups_sites_per_game_and_marks_agreement():
    b = tb.build_board("2026-11-03", SLIPS, VIEWS)
    assert [f"{g['home']} v {g['away']}" for g in b["games"]] == ["Leeds v Hull", "Arsenal v Chelsea"]
    leeds, ars = b["games"]
    assert ars["tips"]["vitibet"]["pick"] == "1" and ars["tips"]["statarea"]["pick"] == "1X"
    assert ars["sites_agree"] is True and ars["model"] == [0.6, 0.25, 0.15] and ars["model_agrees"] is True
    assert leeds["sites_agree"] is False and "model" not in leeds
    assert b["counts"] == {"vitibet": 2, "statarea": 2} and b["paper_only"] is True
    assert "| 20:00 | Arsenal v Chelsea | 1 | 1X | yes | 60%/25%/15% |" in tb.board_md(b)


def test_day_results_per_site_and_agreed_games():
    b = tb.build_board("2026-11-03", SLIPS, VIEWS)
    graded = {"site:vitibet:1": {"status": "won"}, "site:statarea:9": {"status": "won"},
              "site:vitibet:2": {"status": "lost"}}
    r = tb.day_results("2026-11-03", b, graded)["results"]
    assert r["vitibet"] == {"won": 1, "lost": 1, "open": 0}
    assert r["statarea"] == {"won": 1, "lost": 0, "open": 1}
    assert r["sites agree"] == {"won": 1, "lost": 0, "open": 0}


def graded_row(site, fid, p, score, home="A", away="B", ko="2026-11-03T20:00:00Z"):
    return {"poster": f"site:{site}", "post_url": f"site:{site}:{fid}", "status": "won",
            "legs": [{"home": home, "away": away, "kickoff": ko, "p": p, "score": score}]}


def _data(site_p, n, base_p):
    """n graded games where the result is always a home win (one away win for spread); the market and our
    model both say base_p."""
    rows = [graded_row("vitibet", i, site_p, [1, 0], f"H{i}", f"A{i}") for i in range(n)]
    rows[0]["legs"][0]["score"] = [0, 1]
    market = {"2026-11-03": [{"home": f"H{i}", "away": f"A{i}", "p": base_p} for i in range(n)]}
    views = {"2026-11-03": [{"home": f"H{i}", "away": f"A{i}", "p": base_p} for i in range(n)]}
    return rows, market, views


def test_weekly_test_needs_our_model_and_the_market():
    rows, market, views = _data([0.7, 0.15, 0.15], tb.MIN_N, [1 / 3] * 3)
    raw = tb.test(tb.compare(rows, market, views))
    assert raw["vitibet"]["result"] == "pass" and raw["statarea"]["result"] == "collecting"
    no_model = tb.test(tb.compare(rows, market, {}))          # market only: not enough vs our model
    assert no_model["vitibet"]["result"] == "collecting"
    rows, market, views = _data([0.15, 0.15, 0.7], tb.MIN_N, [0.6, 0.25, 0.15])
    assert tb.test(tb.compare(rows, market, views))["vitibet"]["result"] == "fail"


def test_decide_counts_once_a_week_and_needs_two_in_a_row():
    ok = {"vitibet": {"result": "pass", "why": "w", "vs_market": {}, "vs_model": {}}}
    bad = {"vitibet": {"result": "fail", "why": "w", "vs_market": {}, "vs_model": {}}}
    w1 = tb.decide(ok, {}, "2026-W45")
    assert w1["vitibet"]["stage"] == "passed 1/2 weekly checks"
    again = tb.decide(ok, w1, "2026-W45")                     # more runs the same week: no extra pass
    assert again["vitibet"]["passes"] == ["2026-W45"]
    assert tb.decide(ok, again, "2026-W46")["vitibet"]["stage"] == "eligible:shadow"
    reset = tb.decide(bad, again, "2026-W46")                 # a failed week resets the run of passes
    assert reset["vitibet"]["stage"] == "no added value" and reset["vitibet"]["passes"] == []
    midweek_fail = tb.decide(bad, w1, "2026-W45")             # a mid-week dip is not a second look
    assert midweek_fail["vitibet"]["passes"] == ["2026-W45"]


def test_market_index_demargins_last_prices():
    idx = tb.market_index([{"sport": "football", "ko": "2026-11-03T20:00Z", "home": "A", "away": "B",
                            "last": {"p": {"1x2": [2.0, 4.0, 4.0]}}},
                           {"sport": "basketball", "ko": "2026-11-03T20:00Z", "last": {"p": {"win": [1.5, 2.5]}}}])
    p = idx["2026-11-03"][0]["p"]
    assert abs(sum(p) - 1) < 1e-9 and abs(p[0] - 0.5) < 1e-9


def test_run_writes_board_and_stages_and_opens_issue_once(tmp_path, monkeypatch):
    monkeypatch.setattr(tb, "BOARDS", tmp_path / "boards")
    monkeypatch.setattr(tb, "ELIGIBILITY", tmp_path / "eligibility.json")
    monkeypatch.setattr(tb.ts, "FOLDER", tmp_path)
    monkeypatch.setattr(tb, "model_views", lambda d, folder=None: [])
    monkeypatch.setattr(tb.tp, "load_slips", lambda f: SLIPS)
    monkeypatch.setattr(tb.tp, "load_graded", lambda f: [])
    import engine.universe as uv
    monkeypatch.setattr(uv, "load_graded", lambda folder=None: [])
    monkeypatch.setattr(tb, "test", lambda c: {"vitibet": {"result": "pass", "why": "w",
                                                            "vs_market": {}, "vs_model": {"n": 250, "z": 2.1,
                                                                                         "mix_gain": 0.004}}})
    monkeypatch.setattr(tb, "PASSES_NEEDED", 1)
    opened = []
    now = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)
    tb.run(now, open_issue=lambda t, b: opened.append(t) or "https://x/issues/1")
    tb.run(now, open_issue=lambda t, b: opened.append(t) or "https://x/issues/2")
    assert len(opened) == 1                                     # once, not every run
    assert (tmp_path / "boards" / "tips_2026-11-03.md").exists()
    assert json.loads((tmp_path / "eligibility.json").read_text())["vitibet"]["issue"] == "https://x/issues/1"
    lines = tb.report_lines("2026-11-03")
    assert lines[0].startswith("TIP SITES")
    assert any(x.startswith("vitibet: eligible:shadow, mixed into our model: better (z 2.1, 250 games)")
               for x in lines)
    assert "by design" in lines[-1]
