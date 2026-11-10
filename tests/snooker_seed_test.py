"""Snooker Elo seed study (framework#340): name bridge, no guessing, PENDING on no data, live Elo untouched."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import snooker_seed_study as ss  # noqa: E402

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def _rows(n=10):
    return [{"kickoff_utc": f"2025-01-{i + 1:02d}-00-0000", "home": "Kyren Wilson", "away": "Chen Zifan",
             "winner": 1 if i % 3 else 2} for i in range(n)]


def test_bridge_both_name_orders():
    assert "wilson k" in ss.board_keys("Kyren Wilson")
    assert "chen z" in ss.board_keys("Chen Zifan")


def test_resolve_ok_ambiguous_unmatched():
    rows = _rows() + [{"kickoff_utc": "2025-02-01-00-0000", "home": "Kevin Wilson", "away": "Chen Zifan", "winner": 1}]
    elo = ss.seed_elo(rows)
    idx = ss.name_index(elo)
    assert ss.resolve("Chen, Zifan", idx)[1] == "ok"
    assert ss.resolve("Wilson, Kyren", idx)[1] == "ambiguous"      # Kyren and Kevin Wilson both fit 'wilson k'
    assert ss.resolve("Nobody, Joe", idx)[1] == "unmatched"
    only = ss.name_index(ss.seed_elo(_rows()))
    assert ss.resolve("Wilson, Kyren", only)[1] == "ok"


def test_seeded_p_needs_min_games_and_does_not_touch_live():
    elo = ss.seed_elo(_rows(10))
    idx = ss.name_index(elo)
    p, why = ss.seeded_p(elo, idx, "Wilson, Kyren", "Chen, Zifan")
    assert why == "ok" and 0 < p < 1
    elo2 = ss.seed_elo(_rows(2))
    assert ss.seeded_p(elo2, ss.name_index(elo2), "Wilson, Kyren", "Chen, Zifan")[0] is None


def test_pending_without_data_and_brier_pending_when_few():
    assert "PENDING" in ss.render([], [], {}, NOW)
    doc = {"games": {"g": {"home": "Wilson, Kyren", "away": "Chen, Zifan", "sides": {
        "snooker:186||Home": {"first": {"price": 1.9, "fair": 0.52}, "last": {"price": 1.9, "fair": 0.52}, "won": 1},
        "snooker:186||Away": {"first": {"price": 2.0, "fair": 0.48}, "last": {"price": 2.0, "fair": 0.48}, "won": 0}}}}}
    live = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}
    text = ss.render(_rows(10), [("2026-11-10", doc)], live, NOW)
    assert "SEEDED Elo would: **1** of 1" in text and "LIVE Elo gives a chance: **0** of 1" in text
    assert "Brier on graded games: PENDING (1 graded" in text
