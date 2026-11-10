"""Offline test of data/ncaa_players.py, engine/ncaa_projection.py and backtest/ncaa_projection_study.py
(framework#396): box-score parsing, walk-forward (no look-ahead), gate stays closed while CLV is PENDING. No network."""
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

from backtest import ncaa_projection_study as study
from data import ncaa_players as P
from engine import ncaa_projection as E

KEYS = ["minutes", "points", "fieldGoalsMade-fieldGoalsAttempted"]


def blob(h_pl, a_pl):
    def side(tid, pl):
        return {"team": {"id": tid}, "statistics": [{"keys": KEYS, "athletes": [
            {"athlete": {"id": p, "displayName": p}, "starter": i < 5, "didNotPlay": m == 0,
             "stats": [] if m == 0 else [str(m), str(pts), "1-2"]} for i, (p, m, pts) in enumerate(pl)]}]}
    return {"header": {"competitions": [{"competitors": [{"homeAway": "home", "team": {"id": "H"}},
                                                         {"homeAway": "away", "team": {"id": "A"}}]}]},
            "boxscore": {"players": [side("H", h_pl), side("A", a_pl)]}}


pl = [("p1", 30, 15), ("p2", 0, 0), ("p3", 25, "x")]
got = P.players(blob(pl, pl))["H"]
assert [g["p"] for g in got] == ["p1", "p2"], got            # unreadable points row skipped, never guessed
assert got[1]["m"] == 0.0 and got[0]["pts"] == 15

g = {"id": "1", "date": "2026-11-02", "hs": 80.0, "as": 70.0, "total": 140.5, "spread": -6.5}
assert P.game_row({**g, "total": None}, blob(pl, pl)) is None   # no line: PENDING
assert P.game_row(g, {}) is None                                # no box score: PENDING
row = P.game_row(g, blob(pl, pl))
assert row["home"] == "H" and row["line"] == 140.5 and len(row["pl"]["home"]) == 2

with tempfile.TemporaryDirectory() as tmp:
    path, meta = Path(tmp) / "p.jsonl", Path(tmp) / "m.json"
    boards = lambda d: [g] if d == date(2026, 11, 2) else []  # noqa: E731
    assert P.update(date(2026, 11, 4), boards=boards, summary=lambda e: blob(pl, pl), path=path, meta=meta) == 1
    assert P.update(date(2026, 11, 4), boards=boards, summary=lambda e: blob(pl, pl), path=path, meta=meta) == 0
    assert len(P.load(path)) == 1 and len(P.flat(P.load(path))) == 4


def synth(n_days, hot_after=None):
    random.seed(7)
    rows, d0 = [], date(2026, 11, 1)
    teams = [f"T{i}" for i in range(8)]
    for day in range(n_days):
        for k in range(0, 8, 2):
            h, a = teams[k], teams[k + 1]
            hs, as_ = random.gauss(72, 6), random.gauss(70, 6)
            mk = lambda t: [{"p": f"{t}{j}", "n": "", "s": 0, "m": 30 - 2 * j, "pts": round(14 - j)} for j in range(7)]  # noqa: E731
            rows.append({"g": f"{day}-{k}", "day": (d0 + timedelta(day)).isoformat(), "ot": False,
                         "hs": round(hs), "as": round(as_), "line": 142.5, "spread": -2.0,
                         "home": h, "away": a, "pl": {"home": mk(h), "away": mk(a)}})
    return rows


rows = synth(12)
recs = E.walk(rows)
assert recs and all(r["day"] >= "2026-11-06" for r in recs)     # nobody projected before 5 prior games each
assert len(recs) == len(rows) - 5 * 4, (len(recs), len(rows))
# no look-ahead: changing a game's result must not change that game's own projection
bumped = [dict(r) for r in rows]
bumped[-1]["hs"] += 40
assert E.walk(bumped)[-1]["proj"] == recs[-1]["proj"]
pr = E.paired(recs)
assert pr["n"] == 3 * len(recs) and 0 < pr["projection"]["brier"] < 1
gate = E.status(recs)
assert not gate["open"] and any("CLV PENDING" in w for w in gate["why"]) and any("< 150" in w for w in gate["why"])
assert not E.status(recs, {"mean_pts": 1.0})["open"]            # still thin: 12 days of games
assert E.status([])["why"], "empty = closed, PENDING"

oo = study.onoff.summarise(study.onoff.evaluate(P.flat(rows)))
assert oo["all"]["n"] > 0
text = study.render(len(rows), recs, gate, oo)
assert "CLOSED" in text and "Teammate on/off" in text
assert "PENDING" in study.render(0, [], E.status([]), study.onoff.summarise([]))
print("ncaa_projection_test OK")
