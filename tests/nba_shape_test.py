"""NBA game shape: margin / total bands from the sharp line, board line and grading.
A label only — nothing here selects a pick. No network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_shape as shp  # noqa: E402


def test_bands_sum_to_one_and_follow_the_line():
    sh = shp.shape(224.5, -6.5)                  # home favoured by 6.5
    assert abs(sum(sh["margin"].values()) - 1) < 1e-3
    assert abs(sum(sh["total"].values()) - 1) < 2e-3
    assert sh["score"] == [116, 109]
    home = sum(v for k, v in sh["margin"].items() if k.startswith("home"))
    assert home > 0.6
    assert max(sh["total"], key=sh["total"].get) in ("220-229", "210-219")


def test_no_line_no_shape():
    assert shp.shape(None, -3.0) is None and shp.shape(220.0, None) is None
    assert shp.board_line(None, "Lakers", "Celtics") is None


def test_board_line_and_grade():
    sh = shp.shape(224.5, -6.5)
    line = shp.board_line(sh, "Lakers", "Celtics")
    assert line.startswith("Game shape (sharp line, label only): typical 116-109")
    assert "Lakers by" in line and "total" in line
    x = shp.grade(sh, "118-108")                 # home by 10, total 226
    assert x["margin_p"] == sh["margin"]["home 6-10"] and x["total_p"] == sh["total"]["220-229"]
    assert shp.grade(sh, "100-100") is None and shp.grade(sh, None) is None


def test_check_needs_ten():
    sh = shp.shape(224.5, -6.5)
    assert shp.check([(sh, "118-108")] * 9) == []
    out = shp.check([(sh, "118-108")] * 10)
    assert len(out) == 1 and out[0].startswith("Game shape check (10 games)")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("nba_shape_test OK")
