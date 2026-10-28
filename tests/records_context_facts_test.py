"""engine/records/context_facts.py (to-do #7 idea 4)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.records import context_facts as cf  # noqa: E402


def test_signed_facts():
    s = {"home": "Ajax", "away": "PSV", "market": "SB:1||Home", "pick": "Ajax",
         "missing": {"home": 0.2, "away": 0.4}, "news_level": "CAUTION", "league": "KNVB Beker"}
    c = cf.facts(s)
    by = {(f["fact"], f["side"]): f for f in c["facts"]}
    assert c["backs"] == "home"
    assert by[("squad_value_missing", "home")]["direction"] == -1     # our team short: hurts
    assert by[("squad_value_missing", "away")]["direction"] == 1      # their team short: helps
    assert by[("team_news_caution", None)]["size"] == 0.5
    assert ("cup_rotation_risk", None) in by and "referee" in c["unknown"]


def test_totals_pick_unsigned_and_empty():
    c = cf.facts({"home": "A", "away": "B", "market": "SB:18|total=1.5|Over 1.5", "pick": "Over 1.5",
                  "missing": {"home": None, "away": 1.0}, "news_level": "OK", "league": "HNL"})
    assert c["backs"] is None and [f["direction"] for f in c["facts"]] == [0]
    assert cf.facts({})["facts"] == []
    assert cf.pick_side({"market": "SB:16|hcp=-1.5|Away (+1.5)"}) == "away"


if __name__ == "__main__":
    test_signed_facts()
    test_totals_pick_unsigned_and_empty()
    print("records_context_facts_test OK")
