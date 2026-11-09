"""Ice hockey period split (framework#381): record-only calculator, no network."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import hockey_periods as hp  # noqa: E402


def test_split_sums_and_favourite_smallest_first():
    s = hp.split(1.62, 4.6, 5.0)
    assert s["favourite"] == "home"
    for p in s["periods"]:
        assert abs(p["home"] + p["draw"] + p["away"] - 1) < 1e-9
    assert s["smallest_favourite_period"] == 1
    assert s["periods"][0]["draw"] > s["periods"][1]["draw"]


def test_rates_reproduce_full_game():
    ph, pd, pa = hp.devig(1.62, 4.6, 5.0)
    lh, la = hp.solve_rates(ph, pa, pd)
    h, d, a = hp.three_way(lh, la)
    assert max(abs(h - ph), abs(d - pd), abs(a - pa)) < 1e-3


def test_grade_pending_without_prices():
    s = hp.split(1.62, 4.6, 5.0)
    assert hp.grade(s, None)["status"] == "PENDING"
    g = hp.grade(s, {1: {"home": 3.0, "draw": 3.0, "away": 3.0}})
    assert g["periods"][0]["status"] == "OK" and g["periods"][1]["status"] == "PENDING"
    assert g["periods"][0]["home_value"] > 0
