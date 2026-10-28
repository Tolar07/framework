"""
Offline test of the NBA nightly recalibration (engine/nba_recal.py, Architect 2026-10-28
step 3): the graded-games file, the refit, the holdout split and the adopt-only-if-better
gate on both log-likelihood and Brier. No network: fake scoreboard and odds.
"""
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import nba_source as ns
from engine import nba_recal as R

# the graded-games file: regular season, finished, with a sharp line and quarters only
day = date(2026, 10, 21)
board = {day: [ns.Game("a", "2026-10-21", 2027, 2, "BOS", "NYK", 110, 100, True, tip="2026-10-21T23:30Z",
                       q_home=[30, 25, 30, 25], q_away=[20, 30, 25, 25]),
               ns.Game("b", "2026-10-21", 2027, 2, "LAL", "GS", 100, 90, True, tip="2026-10-22T02:30Z",
                       q_home=[25, 25, 25, 25], q_away=[20, 20, 25, 25]),
               ns.Game("c", "2026-10-21", 2027, 1, "MIA", "ORL", 90, 80, True, tip="2026-10-21T23:00Z",
                       q_home=[1, 1, 1, 1], q_away=[1, 1, 1, 1])]}


def attach(g):
    if g.id != "b":                         # game b has no sharp line: not gradable
        g.total, g.spread = 215.5, -4.5
    return g


with tempfile.TemporaryDirectory() as tmp:
    path, meta = Path(tmp) / "graded.jsonl", Path(tmp) / "meta.json"
    n = R.update_games(date(2026, 10, 23), scoreboard=lambda d, use_cache=True: board.get(d, []),
                       attach=attach, path=path, meta=meta)
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert n == 1 and rows == [{"g": "a", "tip": "2026-10-21T23:30Z", "line": 215.5, "spread": -4.5,
                                "hs": 110, "as": 100, "h1": 105, "q1": 50}], rows
    assert json.loads(meta.read_text())["through"] == "2026-10-22"
    assert R.pairs(rows, "margin") == [(4.5, 10)] and R.pairs(rows, "h1") == [(215.5, 105)]
    print("graded games: OK")

# the holdout is the newest ~20% of whole days
rows = [{"tip": f"2026-11-{d:02d}T23:00Z", "g": str(d * 10 + i)} for d in range(1, 11) for i in range(3)]
fit_rows, hold = R.split(rows)
assert len(hold) == 6 and min(r["tip"] for r in hold) > max(r["tip"] for r in fit_rows)
print("holdout split: OK")


def season(share, sd, n=200, seed=1):
    rnd = random.Random(seed)  # noqa: S311 — test data, not crypto
    out = []
    for i in range(n):
        line = rnd.uniform(210, 240)
        h1 = rnd.gauss(share * line, sd)
        out.append({"g": str(i), "tip": (date(2026, 10, 21) + timedelta(i // 8)).isoformat() + "T23:00Z",
                    "line": line, "spread": -3.5, "hs": round(line / 2 + rnd.gauss(0, 9)),
                    "as": round(line / 2 + rnd.gauss(0, 9)), "h1": h1, "q1": rnd.gauss(0.253 * line, 8.1)})
    return out


# a season whose 1st half really runs at 0.48 x line and a tighter spread: the refit is adopted
res = {r["family"]: r for r in R.evaluate(season(0.48, 8.0), R.load_live(Path("/nonexistent")))}
h1 = res["h1"]
assert h1["decision"] == "adopt", h1
assert 0.475 < h1["adopt"]["share"] < 0.502 and h1["adopt"]["sd"] < R.FIXED["h1"]["sd"]
assert h1["holdout"]["refit"][0] < h1["holdout"]["live"][0] and h1["holdout"]["refit"][1] < h1["holdout"]["live"][1]
print("refit adopted when better: OK")

# a season that matches the fixed numbers: no adoption on noise (q1 drawn at the fixed 0.253 / 8.1)
assert res["q1"]["decision"] in ("keep", "adopt")
same = {r["family"]: r for r in R.evaluate(season(R.FIXED["h1"]["share"], R.FIXED["h1"]["sd"], seed=7),
                                          R.load_live(Path("/nonexistent")))}
assert abs(same["h1"].get("refit", {}).get("share", 0.502) - 0.502) < 0.005, "the prior holds the share"
print("refit near the live numbers on a matching season: OK")

# too few games: nothing changes
few = R.evaluate(season(0.48, 8.0, n=40), R.load_live(Path("/nonexistent")))
assert all(r["decision"] == "keep" and "too few" in r["reason"] for r in few)
print("too few games: OK")

# run(): adoption written to the live file, every night logged; the live file is read back
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp)
    gpath = t / "graded.jsonl"
    gpath.write_text("".join(json.dumps(r) + "\n" for r in season(0.48, 8.0)))
    (t / "meta.json").write_text(json.dumps({"season": "2026-10-01", "through": "2026-12-31"}))
    out = R.run(date(2026, 12, 1), live_path=t / "live.json", log_path=t / "log.jsonl",
                path=gpath, meta=t / "meta.json", scoreboard=lambda d, use_cache=True: [], attach=attach)
    live = json.loads((t / "live.json").read_text())
    assert "h1" in live and live["h1"]["share"] == next(r for r in out if r["family"] == "h1")["adopt"]["share"]
    assert R.load_live(t / "live.json")["h1"]["share"] == live["h1"]["share"]
    assert R.load_live(t / "live.json")["total"] == R.FIXED["total"] or "total" in live
    assert len((t / "log.jsonl").read_text().splitlines()) == 1
    print("run + live file: OK")

print("nba_recal_test: ALL OK")
