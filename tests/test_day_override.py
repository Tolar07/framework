import json

from engine import day_override as d
from engine import short_legs as sl


def test_get_and_struck(tmp_path):
    f = tmp_path / "o.json"
    f.write_text(json.dumps({"2026-11-02": {"forced_edge": 0.0, "no_single": ["Tenerife"]}}))
    ov = d.get("2026-11-02", f)
    assert ov["forced_edge"] == 0.0
    assert d.struck(ov, "tenerife") and not d.struck(ov, "Oviedo")
    assert d.get("2026-11-03", f) == {}
    assert d.get("2026-11-02", tmp_path / "missing.json") == {}


def test_with_edge_override():
    class Q:
        price = 1.30
    c = [(0.78, 0, "k", 0, 0, Q())]            # 0.78 - 1/1.30 = +0.6 pts
    assert sl.with_edge(c) == []
    assert sl.with_edge(c, 0.0) == c


def test_shipped_file_parses():
    assert d.get("2026-11-02")["forced_edge"] == 0.0


def test_only_singles_allow_list():
    ov = {"only_singles": ["Newcastle"], "no_single": []}
    assert not d.struck(ov, "Newcastle") and d.struck(ov, "Rakow")
    assert len(d.get("2026-11-02")["only_singles"]) == 12
