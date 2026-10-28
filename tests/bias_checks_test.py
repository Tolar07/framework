"""engine/bias_checks.py — bands, as-of table, both sides on a single, ledger never breaks."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import bias_checks as bc  # noqa: E402


def _recs():
    rows = []
    for i in range(100):     # short favourites at 1.25 that land 90% (fair 0.76): too long
        rows.append({"key": "SB:18|total=1.5|Over 1.5", "won": int(i % 10 != 0), "price": 1.25,
                     "fair": 0.76, "sport": "football", "ko": "2026-10-10T15:00Z"})
    for i in range(100):     # longshots at 5.0 that land 10% (fair 0.19): too short
        rows.append({"key": "SB:1||Away", "won": int(i % 10 == 0), "price": 5.0,
                     "fair": 0.19, "sport": "football", "ko": "2026-10-10T15:00Z"})
    rows.append({"key": "SB:18|total=1.5|Over 1.5", "won": 0, "price": 1.25, "fair": 0.76,
                 "sport": "football", "ko": "2026-10-20T15:00Z"})                  # after the cut
    return rows


def test_band():
    assert bc.band(1.25) == "1.20-1.30" and bc.band(1.99) == "1.75-2.00"
    assert bc.band(7) == "4.00+" and bc.band(1.0) is None and bc.band(None) is None and bc.band("x") is None


def test_table_is_as_of_and_signed():
    t = bc.table(_recs(), before="2026-10-15")
    fav = t["football|SB:18|1.20-1.30"]
    assert fav["n"] == 100 and fav["bias"] > 0.1 and 0 < fav["shrunk"] < fav["bias"]
    assert t["football|SB:1|4.00+"]["bias"] < -0.05
    assert bc.table(_recs())["football|SB:18|1.20-1.30"]["n"] == 101


def test_annotate_both_sides():
    t = bc.table(_recs(), before="2026-10-15")
    b = bc.annotate({"market": "SB:18|total=1.5|Over 1.5", "price": 1.25}, t)
    assert b["short_leg"] is True
    assert b["yes"]["cell"] == "SB:18|1.20-1.30" and b["yes"]["bias"] > 0
    assert b["no"]["cell"] == "*|4.00+" and b["no"]["bias"] < 0      # price 5.0: the other side
    assert bc.annotate({"market": "SB:18||x", "price": None}, t) is None


def test_annotate_doc_never_raises(monkeypatch=None):
    bc._TAB.clear()
    bc._TAB["2026-10-15"] = bc.table(_recs(), before="2026-10-15")
    doc = {"singles": [{"market": "SB:1||Away", "price": 4.5}], "study": [{"price": "bad"}]}
    assert bc.annotate_doc(doc, "2026-10-15") == "bias recorded 1"
    assert "bias" in doc["singles"][0] and "bias" not in doc["study"][0]
    bc._TAB.clear()
    bc._TAB["x"] = None   # type: ignore[assignment]
    assert bc.annotate_doc({"singles": [{"market": "SB:1||Away", "price": 2}]}, "x").startswith("bias skipped")
    bc._TAB.clear()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("bias_checks_test OK")
