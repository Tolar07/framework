"""Home-edge shadow: scores both Elos walk-forward, never touches the live table. No network."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import home_edge_shadow as hes  # noqa: E402
from engine import multisport as ms  # noqa: E402


def _games(n=200):
    t = ["A", "B", "C", "D"]
    return [{"home": t[i % 4], "away": t[(i + 1) % 4], "kickoff_utc": f"2026-01-01T{i // 60:02d}:{i % 60:02d}",
             "winner": 1 if i % 3 else 2} for i in range(n)]


def test_pending_until_scored():
    assert hes.summary("rugby", hes.load("nope_sport"))["status"] == "PENDING"


def test_scores_both_and_matches_live_learn():
    games = _games()
    live = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}
    st = {"ratings": {}, "games": {}, "seen": [], "n": 0, "live_sq": 0.0, "cand_sq": 0.0}
    n = hes.learn("rugby", st, games, live)
    ms.learn(live, games)
    assert n == len(games)
    assert st["n"] == live["brier"][1] > 0
    assert abs(st["live_sq"] - live["brier"][0]) < 1e-9      # shadow's live score == the live Elo's own record
    s = hes.summary("rugby", st)
    assert s["status"] == "RECORD" and s["candidate_better"] == (s["candidate_brier"] < s["live_brier"])


def test_live_table_untouched_and_idempotent():
    games = _games(60)
    live = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}
    before = copy.deepcopy(live)
    st = {"ratings": {}, "games": {}, "seen": [], "n": 0, "live_sq": 0.0, "cand_sq": 0.0}
    hes.learn("rugby", st, games, live)
    assert live == before
    assert hes.learn("rugby", st, games, live) == 0


def test_other_sports_ignored():
    st = {"ratings": {}, "games": {}, "seen": [], "n": 0, "live_sq": 0.0, "cand_sq": 0.0}
    assert hes.learn("darts", st, _games(10), {"ratings": {}, "games": {}}) == 0
