"""The scoreline table: top scores, match shape, ledger grid and grading.
A label only — nothing here selects a pick. No network."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import scoreline as sl  # noqa: E402
from engine.dixon_coles import score_matrix  # noqa: E402


def probs(m):
    return SimpleNamespace(home_team="Leeds", away_team="Hull", matrix=m)


def test_top_scores_and_shape_come_from_the_table():
    m = score_matrix(1.6, 0.9, -0.1)
    top = sl.top_scores(m)
    i, j = np.unravel_index(np.argmax(m), m.shape)
    assert top[0] == (f"{i}-{j}", float(m[i, j])) and top[0][1] >= top[1][1] >= top[2][1]
    sh = sl.shape(m)
    assert abs(sh["goals_0_1"] + sh["goals_2_3"] + sh["goals_4p"] - 1) < 1e-9
    assert abs(sh["home_cs"] - m[:, 0].sum()) < 1e-12
    line = sl.board_line(probs(m))
    assert line.startswith(f"Likely scores (model, label only): {i}-{j}")
    assert "clean sheet Leeds" in line


def test_no_table_no_scoreline():
    # market-implied fixtures carry no matrix: nothing is invented (HR35)
    assert sl.board_line(probs(None)) is None and sl.ledger_grid(probs(None)) is None


def test_grid_and_grading():
    m = score_matrix(1.4, 1.1, -0.1)
    g = sl.ledger_grid(probs(m))
    assert len(g) == sl.GRID and all(len(r) == sl.GRID for r in g)
    best = sl.top_scores(m, 1)[0][0]
    x = sl.grade(g, best)
    assert x["rank"] == 1 and abs(x["p"] - g[int(best[0])][int(best[2])]) < 1e-12
    far = sl.grade(g, "7-0")                 # beyond the grid: leftover chance
    assert far["rank"] is None and 0 <= far["p"] < 0.01
    assert sl.grade(g, "no-90min-result") is None


def test_check_needs_ten_and_reports():
    g = sl.ledger_grid(probs(score_matrix(1.4, 1.1, -0.1)))
    assert sl.check([(g, "1-1")] * 9) == []
    out = sl.check([(g, "1-1")] * 6 + [(g, "3-2")] * 4 + [(g, "PENDING")] * 3)
    assert len(out) == 1 and out[0].startswith("Scoreline check (10 rated fixtures)")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("scoreline_test OK")
