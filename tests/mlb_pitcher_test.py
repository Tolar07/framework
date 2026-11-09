"""MLB starting-pitcher shadow (framework#382): walk-forward ratings, no peeking, PENDING when thin, no network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import mlb_pitcher_backtest as mb  # noqa: E402
from engine.mlb_pitcher import Ratings, win_prob  # noqa: E402


def _g(a="BOS", b="NYY", spa="1", spb="2", f5a=2.0, f5b=3.0):
    return {"a": a, "b": b, "spa": spa, "spb": spb, "f5a": f5a, "f5b": f5b}


def test_win_prob_symmetry_and_sum():
    w, t = win_prob(2.5, 2.5)
    assert abs(w - (1 - w - t)) < 1e-9 and 0 < t < 0.3
    w2, _ = win_prob(3.5, 2.0)
    assert w2 > 0.6


def test_pending_until_league_sample_then_starter_matters():
    r = Ratings()
    assert r.predict(_g()) is None                       # thin sample -> PENDING, never invented
    for i in range(300):                                  # starter "9" is dominant, "8" is poor
        r.update(_g(a="T1", b="T2", spa="8", spb="9", f5a=0.0 if i % 2 else 1.0, f5b=5.0))
        r.update(_g(a="T3", b="T4", spa="7", spb="7", f5a=2.0, f5b=2.0))
    p_good = r.predict(_g(a="T1", b="T2", spa="7", spb="9"))
    p_bad = r.predict(_g(a="T1", b="T2", spa="7", spb="8"))
    assert p_good["full_a"] < p_bad["full_a"]             # facing the dominant starter lowers the visitor's chance
    assert r.predict(_g(spa=None))["missing_sp"] is True


def test_predict_does_not_peek():
    r = Ratings()
    for _ in range(300):
        r.update(_g(f5a=2.0, f5b=2.0))
    before = r.predict(_g())
    r.predict(_g())
    assert before == r.predict(_g())                      # predict alone never changes state


def test_update_skips_short_linescore():
    r = Ratings()
    r.update(_g(f5a=None))
    assert r.lg == [0.0, 0.0]


def test_extras_reads_starters_and_first_five():
    ev = {"competitions": [{"competitors": [
        {"homeAway": "home", "probables": [{"playerId": 7}], "linescores": [{"value": 1}] * 9},
        {"homeAway": "away", "probables": [], "linescores": [{"value": 0}] * 3}]}]}
    e = mb.extras(ev)
    assert e["spb"] == "7" and e["f5b"] == 5.0 and e["spa"] is None and e["f5a"] is None
