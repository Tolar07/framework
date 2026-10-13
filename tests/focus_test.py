"""Board focus (engine/focus.py): on a focus day only the focus competitions
reach the board; every other deploy pick becomes a study pick, recorded and
graded but never sent or counted as a board single. No network."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import flashscore_results as fs  # noqa: E402
from engine import focus  # noqa: E402
from engine import markets as mkt  # noqa: E402
from engine import picks_ledger as pl  # noqa: E402

FEED = ("SA÷1¬~ZA÷ENGLAND: League Two¬~AA÷x1¬AD÷1791036000¬AB÷3¬AC÷3¬AE÷Bristol Rovers"
        "¬AF÷Crewe¬AG÷2¬AH÷1¬")


def fx(home, away, league, deploy=True):
    probs = SimpleNamespace(home_team=home, away_team=away, p_home=0.5, p_draw=0.3,
                            p_away=0.2, p_over_15=0.7, p_over_25=0.45, p_over_35=0.2,
                            p_btts_yes=0.5)
    return SimpleNamespace(fixture=f"{home} v {away} ({league})", probs=probs,
                           kickoff_date="2026-10-03", prob_source="model",
                           on_deploy_shortlist=deploy, best_market_key=mkt.HOME,
                           best_price=1.8, best_model_prob=0.6, tier="AGREE",
                           certainty="HIGH", booking_code=None)


def test_leagues_for_reads_the_day():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "focus.json"
        p.write_text(json.dumps({"2026-10-13": ["Champions League"]}))
        assert focus.leagues_for("2026-10-13", p) == ["Champions League"]
        assert focus.leagues_for("2026-10-14", p) == [], "an ordinary day"
        assert focus.leagues_for(None, p) == []
        assert focus.leagues_for("2026-10-13", Path(d) / "missing.json") == []


def test_ordinary_day_changes_nothing():
    board = [fx("Lens", "Sporting", "Champions League"), fx("Bristol Rvs", "Crewe", "League Two")]
    assert focus.demote(board, []) == 0
    assert all(b.on_deploy_shortlist for b in board)
    assert all(focus.on_board(b, []) for b in board)


def test_focus_day_demotes_the_rest_to_study_and_grades_it():
    ucl, l2 = fx("Lens", "Sporting", "Champions League"), fx("Bristol Rvs", "Crewe", "League Two")
    board = [ucl, l2]
    assert focus.demote(board, ["Champions League"]) == 1
    assert ucl.on_deploy_shortlist and not getattr(ucl, "study_pick", False)
    assert not l2.on_deploy_shortlist and l2.study_pick
    assert "study only" in l2.rejection_reason
    assert [b for b in board if focus.on_board(b, ["Champions League"])] == [ucl]
    with tempfile.TemporaryDirectory() as d:
        pl.LEDGER_DIR = Path(d)
        pl.SUPERSEDED_DIR = Path(d) / "superseded"
        path = pl.write_ledger("2026-10-03", board, [], [], [], {}, {}, None)
        doc = json.loads(path.read_text())
        assert [s["fixture"] for s in doc["singles"]] == ["Lens v Sporting"]
        assert [s["fixture"] for s in doc["study"]] == ["Bristol Rvs v Crewe"]
        assert doc["study"][0]["study"] is True
        assert len(doc["rated"]) == 2, "every fixture is still rated"
        flags = pl.grade_all(fs.parse_feed(FEED), today="2026-10-04")
        doc = json.loads(path.read_text())
        assert doc["study"][0]["result"] == "won", doc["study"][0]
        assert any("0 graded, 1 pending" in f for f in flags), \
            f"study picks are not counted as board singles: {flags}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("focus_test: OK")
