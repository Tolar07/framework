import json

from scripts import clv_scorecard as C


def _day(tmp, d, singles, accas=()):
    (tmp / f"picks_{d}.json").write_text(json.dumps({"date": d, "singles": singles, "accas": list(accas)}))


def test_moe_and_cell():
    assert C.moe(1, 0.1) is None
    assert abs(C.moe(100, 0.1) - 0.0196) < 1e-9
    assert "▲" in C.clv_cell(100, 0.05, 0.1)       # 5% +- 2% excludes zero
    assert "○" in C.clv_cell(100, 0.005, 0.1)
    assert "(thin)" in C.clv_cell(10, 0.05, 0.01)
    assert C.clv_cell(0, None, None) == "CLV n/a"


def test_scorecard_builds_and_stays_short(tmp_path):
    singles = [{"market": "SB:18|total=2.5|Over 2.5", "price": 2.0, "clv": 4.0 + i % 3, "result": "won" if i % 2 else "lost"}
               for i in range(40)]
    _day(tmp_path, "2026-10-10", singles, [{"odds": 2.0, "result": "won"}])
    text = C.scorecard("2026-10-21", 28, tmp_path, tmp_path / "none", tmp_path / "none.json")
    assert "CLV SCORECARD" in text and "n=40" in text and "Accas: CLV n/a" in text
    assert "summary not available" in text and len(text) <= C.MAX_CHARS
