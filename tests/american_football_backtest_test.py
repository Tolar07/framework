"""American football walk-forward backtest (framework#339/#352): nflverse CSV parse, no-peeking Elo replay,
held-out report. No network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import american_football_backtest as af  # noqa: E402

HEAD = "season,gameday,home_team,away_team,home_score,away_score,home_moneyline,away_moneyline\n"


def _csv(n=1400):
    teams = ["A", "B", "C", "D", "E", "F"]
    rows = []
    for i in range(n):
        h, a = teams[i % 6], teams[(i * 5 + 1) % 6]
        if h == a:
            a = teams[(i + 1) % 6]
        season = 2006 + i // 70
        hs = 24 if teams.index(h) < teams.index(a) else 17
        rows.append(f"{season},{season}-{1 + i % 12:02d}-{1 + i % 28:02d},{h},{a},{hs},20,-150,130")
    rows.append("2020,2020-01-01,A,B,20,20,-110,-110")   # tie: skipped
    rows.append("2020,2020-01-02,A,B,x,20,-110,-110")    # bad row: skipped
    return HEAD + "\n".join(rows)


def test_american_to_decimal():
    assert abs(af.american_to_decimal(-200) - 1.5) < 1e-9
    assert abs(af.american_to_decimal(150) - 2.5) < 1e-9


def test_load_skips_ties_and_bad_rows():
    games = af.load(_csv())
    assert len(games) == 1400 and all(g["y"] in (0.0, 1.0) for g in games)
    assert 0.5 < af.fair_home(games[0]) < 0.7


def test_replay_never_peeks_and_waits_for_min_games():
    games = af.load(_csv())
    probs = af.replay(games, 24.0, 0.0)
    assert probs[0] is None and any(p is not None for p in probs)
    flipped = [dict(g, y=1 - g["y"]) if i == 700 else g for i, g in enumerate(games)]
    assert af.replay(flipped, 24.0, 0.0)[:701] == probs[:701]   # a later result cannot change an earlier chance


def test_run_reports_heldout_and_record_only():
    text = af.run(af.load(_csv()))
    assert "Settings tried: **54**" in text and "Record only" in text
