"""Every rated fixture is recorded, graded from results and scored as a model
check — without touching how picks are chosen. No network."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import flashscore_results as fs  # noqa: E402
from engine import picks_ledger as pl  # noqa: E402

FEED = ("SA÷1¬~ZA÷ENGLAND: League Two¬~AA÷x1¬AD÷1791036000¬AB÷3¬AC÷3¬AE÷Bristol Rovers"
        "¬AF÷Crewe¬AG÷2¬AH÷1¬~AA÷x2¬AD÷1791036000¬AB÷3¬AC÷11¬AE÷Grimsby¬AF÷Shrewsbury"
        "¬AG÷1¬AH÷1¬")


def fixture(home, away, src="model", shortlist=False):
    probs = SimpleNamespace(home_team=home, away_team=away, p_home=0.5, p_draw=0.3,
                            p_away=0.2, p_over_15=0.7, p_over_25=0.45, p_over_35=0.2,
                            p_btts_yes=0.5)
    return SimpleNamespace(fixture=f"{home} v {away} (League Two)", probs=probs,
                           kickoff_date="2026-10-03", prob_source=src,
                           on_deploy_shortlist=shortlist, best_market_key=None)


def test_records_every_rated_fixture_and_grades_it():
    with tempfile.TemporaryDirectory() as d:
        pl.LEDGER_DIR = Path(d)
        board = [fixture("Bristol Rvs", "Crewe"), fixture("Grimsby", "Shrewsbury", "market"),
                 SimpleNamespace(fixture="No Model v Fixture (League Two)", probs=None,
                                 on_deploy_shortlist=False, best_market_key=None)]
        path = pl.write_ledger("2026-10-03", board, [], [], [], {}, {}, None)
        doc = json.loads(path.read_text())
        assert doc["singles"] == [], "picks are unchanged: nothing on the shortlist"
        assert [r["fixture"] for r in doc["rated"]] == ["Bristol Rvs v Crewe",
                                                        "Grimsby v Shrewsbury"]
        assert doc["rated"][0]["p"] == [0.5, 0.3, 0.2, 0.7, 0.45, 0.2, 0.5]
        assert doc["rated"][1]["src"] == "market"

        flags = pl.grade_all(fs.parse_feed(FEED), today="2026-10-04")
        doc = json.loads(path.read_text())
        assert doc["rated"][0]["ft"] == "2-1"
        assert doc["rated"][1]["ft"] == "no-90min-result", "after pens is never a 90-min score"
        assert any("2/2 rated fixtures graded" in f for f in flags), flags


def test_old_ledgers_are_not_regraded():
    with tempfile.TemporaryDirectory() as d:
        pl.LEDGER_DIR = Path(d)
        path = pl.write_ledger("2026-10-03", [fixture("Bristol Rvs", "Crewe")],
                               [], [], [], {}, {}, None)
        pl.grade_all(fs.parse_feed(FEED), today="2026-11-30")
        assert json.loads(path.read_text())["rated"][0]["ft"] is None


def test_model_check_scores_model_rows_only():
    model = [{"src": "model", "p": [0.6, 0.25, 0.15, 0.8, 0.5, 0.25, 0.5], "ft": "2-0"}] * 12
    market = [{"src": "market", "p": [0.0, 0.0, 1.0, 0, 0, 0, 0], "ft": "2-0"}] * 50
    lines = pl.model_check(model + market)
    assert lines and "12 rated fixtures" in lines[0], lines
    # 1X2 Brier for p=(.6,.25,.15), home win: .16 + .0625 + .0225 = .245
    assert "Brier 1X2 0.245" in lines[0], lines[0]
    # Over 2.5: p=.5, 2 goals -> under: .25 ; BTTS: p=.5, no -> .25
    assert "Over 2.5 0.250" in lines[0] and "BTTS 0.250" in lines[0]
    assert "60-70% → 100%" in lines[1], lines[1]


def test_model_check_needs_enough_results():
    assert pl.model_check([{"src": "model", "p": [0.5] * 7, "ft": "1-0"}] * 9) == []
    assert pl.model_check([{"src": "model", "p": [0.5] * 7, "ft": None}] * 30) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("rated_ledger_test: OK")
