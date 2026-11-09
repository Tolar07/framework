"""Baseball (MLB) walk-forward backtest (framework#346/#352): ESPN parse, closing-price median, no-peeking replay,
held-out report. No network (a fake ESPN fetcher)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import baseball_backtest as bb  # noqa: E402


def _event(i, season=2023, stype=2, done=True, sa=3, sh=5, neutral=False):
    return {"id": str(i), "date": f"{season}-06-{1 + i % 28:02d}T23:05Z", "season": {"type": stype, "year": season},
            "competitions": [{"neutralSite": neutral, "status": {"type": {"completed": done}},
                              "competitors": [{"homeAway": "home", "team": {"abbreviation": "NYY"}, "score": str(sh)},
                                              {"homeAway": "away", "team": {"abbreviation": "BOS"}, "score": str(sa)}]}]}


def _odds(away, home, provider="Bet X", close=True):
    def side(v):
        return {"close": {"moneyLine": {"american": str(v)}}} if close else {"moneyLine": v}
    return {"provider": {"name": provider}, "awayTeamOdds": side(away), "homeTeamOdds": side(home)}


def test_american_to_decimal():
    assert abs(bb.american(-200) - 1.5) < 1e-9
    assert abs(bb.american("+150") - 2.5) < 1e-9
    assert bb.american("EVEN") is None and bb.american(None) is None and bb.american(50) is None


def test_games_of_day_keeps_finished_regular_and_playoff_only():
    board = {"events": [_event(1), _event(2, stype=1), _event(3, done=False), _event(4, sa=4, sh=4),
                        _event(5, stype=3, sa=7, sh=2), {"id": "9", "season": {"type": 2, "year": 2023}}]}
    got = bb.games_of_day(board)
    assert [g["id"] for g in got] == ["1", "5"]
    assert got[0]["y"] == 0.0 and got[1]["y"] == 1.0          # y = 1 when the visitor (side a) won
    assert bb.games_of_day(None) == []


def test_close_prices_median_skips_live_and_wide_books():
    odds = {"items": [_odds(-110, -110), _odds(-120, 100), _odds(150, -170, provider="Live Odds"),
                      _odds(-300, -300, provider="Wide")]}
    pa, pb = bb.close_prices(odds)
    assert abs(pa - (bb.american(-110) + bb.american(-120)) / 2) < 1e-9 and pb > 1.9
    assert bb.close_prices({"items": []}) is None and bb.close_prices(None) is None
    fallback = {"items": [_odds(-130, 110, close=False)]}      # no 'close' block: the last line is used
    assert bb.close_prices(fallback) is not None


def _fake_games(n=900):
    teams = ["A", "B", "C", "D", "E", "F"]
    games = []
    for i in range(n):
        a, b = teams[i % 6], teams[(i * 5 + 1) % 6]
        if a == b:
            b = teams[(i + 1) % 6]
        season = 2019 + i // 130
        y = 1.0 if teams.index(a) < teams.index(b) else 0.0
        g = {"id": str(i), "key": f"{season}-06-{1 + i % 28:02d}T{i % 24:02d}:{i % 60:02d}", "season": season,
             "a": a, "b": b, "y": y, "neutral": False, "pa": 2.0, "pb": 1.9}
        g["mkt"] = bb.devig(g["pa"], g["pb"])
        games.append(g)
    return sorted(games, key=lambda g: (g["key"], g["a"], g["b"]))


def test_probs_never_peek_and_wait_for_min_games():
    games = _fake_games()
    probs = bb.probs_for(games, 8.0, 24.0, 1.0)
    assert probs[0] is None and any(p is not None for p in probs)
    flipped = [dict(g, y=1 - g["y"]) if i == 500 else g for i, g in enumerate(games)]
    assert bb.probs_for(flipped, 8.0, 24.0, 1.0)[:501] == probs[:501]   # a later result cannot change an earlier chance


def test_load_with_fake_espn_and_skips_unpriced(tmp_path, monkeypatch):
    monkeypatch.setattr(bb, "CACHE", tmp_path)
    monkeypatch.setattr(bb.time, "sleep", lambda s: None)

    def get(url):
        if "scoreboard?dates=20230601" in url:
            return {"events": [_event(1), _event(2)]}
        if "scoreboard" in url:
            return {"events": []}
        return {"items": [_odds(-110, -110)]} if "/events/1/" in url else {"items": []}
    games, notes = bb.load(get, seasons=(2023,))
    assert [g["id"] for g in games] == ["1"] and games[0]["pa"] == games[0]["pb"]
    assert abs(games[0]["mkt"] - 0.5) < 1e-9
    assert any("1 of 2 games without a closing price" in n for n in notes)
    empty, notes2 = bb.load(lambda url: {"events": []}, seasons=(2022,))
    assert empty == [] and "no games loaded - PENDING" in notes2[0]


def test_run_reports_heldout_and_record_only():
    text = bb.run(_fake_games(), ["note"])
    assert "reported on **2023-2025 only**" in text or "only**" in text
    assert "Record only" in text and "Not loaded: note" in text
    assert f"**{len(bb.KS) * len(bb.HOME) * len(bb.CARRY) * len(bb.MKT_W) + len(bb.EDGES) * 2}**" in text
