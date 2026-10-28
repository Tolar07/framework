"""engine/records/exposure.py (to-do #7 idea 5)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.records import exposure as ex  # noqa: E402


def test_caps_and_acca_pairs():
    singles = [{"fixture": f"A{i} v B{i}", "league": "EPL", "chance": 0.9 - i / 100, "stake_pct": 1}
               for i in range(6)] + [{"fixture": "C v D", "league": "SPL", "chance": 0.7}]
    doc = {"singles": singles, "accas": [{"name": "A1", "chance": 0.5, "legs": ["A0 v B0", "A1 v B1", "C v D"]}],
           "rated": [{"fixture": "X v Y", "league": "SPL"}]}
    ex.annotate_doc(doc, "2026-10-28")
    ranks = [s["exposure"]["league_rank"] for s in singles[:6]]
    assert ranks == [1, 2, 3, 4, 5, 6] and [s["exposure"]["over_cap"] for s in singles[:6]].count(True) == 2
    a = doc["exposure"]["accas"][0]
    assert a["same_league_pairs"] == 1 and a["chance_corr"] > a["chance_indep"]
    assert doc["exposure"]["over_cap"] == 2 and doc["exposure"]["stake_pct"] == 6
    assert ex.annotate_doc({}, "x").startswith("exposure 0")


if __name__ == "__main__":
    test_caps_and_acca_pairs()
    print("records_exposure_test OK")
