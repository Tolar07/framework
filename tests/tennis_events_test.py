"""engine/tennis_events.py, monitor/tennis_events_run.py, backtest/tennis_events_study.py (framework #559). Offline."""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import tennis_events_study as study  # noqa: E402
from engine import tennis_events as te  # noqa: E402
from monitor import tennis_events_run as run  # noqa: E402

# 1. agrees with the board: the model's win chance equals the board's, for both formats and both tours
for p in (0.2, 0.5, 0.63, 0.9):
    for comp in ("ATP Paris, France Men Singles", "Wimbledon, Great Britain Men Singles", "WTA Linz Women Singles"):
        r = te.predict(p, comp)
        assert r and abs(r["win_home"] - p) < 2e-3, (p, comp, r)
print("agrees with the board's win chance: OK")

# 2. distributions are proper and consistent
r = te.predict(0.6, "ATP Paris Men Singles")
assert abs(sum(r["set_scores"].values()) - 1) < 1e-3
two_nil = r["set_scores"]["2-0"] + r["set_scores"]["0-2"]
assert abs(sum(v for k, v in r["set_scores"].items() if k in ("2-0", "2-1")) - 0.6) < 2e-3
assert all(r["over"][a] >= r["over"][b] for a, b in zip(list(r["over"])[:-1], list(r["over"])[1:]))   # over falls with the line
assert 0 < r["tiebreak"] < 1 and 15 < r["expected_games"] < 40
assert r["aces"].startswith("PENDING") and r["double_faults"].startswith("PENDING")     # no invented serve data
print("distributions: OK")

# 3. a lopsided match has fewer games and fewer sets than an even one; best of 5 has more games
even, lop = te.predict(0.5, "ATP X Men Singles"), te.predict(0.92, "ATP X Men Singles")
assert lop["expected_games"] < even["expected_games"]
assert lop["set_scores"]["2-0"] > even["set_scores"]["2-0"]
assert te.predict(0.5, "Wimbledon Men Singles")["expected_games"] > even["expected_games"] + 8
assert te.best_of("Wimbledon Women Singles") == 3 and te.best_of("Challenger Wimbledon Men Singles") == 3
print("shape: OK")

# 4. PENDING, never invented: no price, doubles, out of range
assert te.predict(None, "ATP X Men Singles") is None
assert te.predict(0.6, "ATP X Men Doubles", home="A / B") is None
assert te.predict(1.0, "ATP X Men Singles") is None
assert te.home_chance({}) is None
sides = {"tennis:186||Home": {"first": {"price": 2.0}}, "tennis:186||Away": {"last": {"price": 2.0}},
         "tennis:189|total=21.5|Over 21.5": {}, "tennis:189|total=22.5|Under 22.5": {}}
assert abs(te.home_chance(sides) - 0.5) < 1e-9 and te.total_lines(sides) == [21.5, 22.5]
assert te.games_from_periods([[6, 4], [7, 6], [6, 3]]) == (32, 3, True) and te.games_from_periods(None) is None
print("pending: OK")

# 5. study: parse orients by name, scores from the favourite's side; baseline and model both produce numbers
row = {"ATP": "1", "Date": "43465", "Surface": "Hard", "Best of": "3", "Winner": "Zed Z.", "Loser": "Abe A.", "Comment": "Completed",
       "PSW": "1.5", "PSL": "2.7", "W1": "6", "L1": "4", "W2": "7", "L2": "6"}
parsed = study.parse([row, {**row, "Comment": "Retired"}, {**row, "PSW": ""}])
assert len(parsed) == 1 and parsed[0]["tb"] and parsed[0]["tot"] == 23 and parsed[0]["score"] == "2-0" and parsed[0]["p"] > 0.5
assert study.cell_dist(30, 3, 0.62) is not None

# 6. runner + grading on a fixture board
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    run.BOARD, run.OUT = t / "board", t / "out"
    run.BOARD.mkdir()
    sd = {"tennis:186||Home": {"last": {"price": 1.6}}, "tennis:186||Away": {"last": {"price": 2.4}},
          "tennis:189|total=21.5|Over 21.5": {}, "tennis:189|total=21.5|Under 21.5": {}}
    games = {"m1": {"comp": "ATP Paris Men Singles", "home": "A", "away": "B", "ko": "x", "sides": sd,
                    "result": {"final": [2, 1], "periods": [[6, 4], [4, 6], [7, 6]], "winner": 1}},
             "m2": {"comp": "ATP Paris Men Doubles", "home": "A / B", "away": "C / D", "ko": "x", "sides": sd, "result": None}}
    (run.BOARD / "ms_2026-11-06.json").write_text(json.dumps({"games": games}), encoding="utf-8")
    doc = run.build_day("2026-11-06", {}, {})
    assert doc["label"] == "shadow" and doc["games"][0]["model"] and doc["games"][1]["model"] is None
    assert list(doc["games"][0]["model"]["over"]) == ["21.5"]            # only SportyBet's own listed line
    run.OUT.mkdir()
    (run.OUT / "2026-11-06.json").write_text(json.dumps(doc), encoding="utf-8")
    rec = run.grade_files(date(2026, 11, 8))
    d = rec["days"]["2026-11-06"]
    assert d["matches"] == 1 and d["over_n"] == 1 and d["set_n"] == 1 and rec["total"]["tb_logloss"] > 0
print("study / runner / grading: OK")
