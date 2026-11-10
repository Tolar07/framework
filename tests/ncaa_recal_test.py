"""Offline test of engine/ncaa_recal.py and backtest/ncaa_blend_study.py (framework#395): graded-games file,
holdout split, adopt-only-if-better gate, PENDING when thin. No network."""
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

from backtest import ncaa_blend_study as bs
from engine import ncaa_recal as R

board = {date(2026, 11, 2): [
    {"id": "a", "hs": 80, "as": 70, "h1": 38, "ot": False},
    {"id": "b", "hs": 60, "as": 61, "h1": 30, "ot": False},      # no sharp line: not gradable
]}
lines = {"a": {"total": 140.5, "spread": -6.5, "ml_home": 1.3, "ml_away": 3.6}, "b": None}

with tempfile.TemporaryDirectory() as tmp:
    path, meta = Path(tmp) / "g.jsonl", Path(tmp) / "m.json"
    n = R.update_games(date(2026, 11, 4), scoreboard=lambda d: board.get(d, []), line=lambda g: lines[g["id"]],
                       path=path, meta=meta)
    rows = R.load(path)
    assert n == 1 and rows[0]["g"] == "a" and rows[0]["line"] == 140.5 and rows[0]["day"] == "2026-11-02", rows
    assert json.loads(meta.read_text())["through"] == "2026-11-03"
    # incremental: a second run adds nothing and does not duplicate
    assert R.update_games(date(2026, 11, 4), scoreboard=lambda d: board.get(d, []), line=lambda g: lines[g["id"]],
                          path=path, meta=meta) == 0
    assert len(R.load(path)) == 1
    assert R.pairs(rows, "margin") == [(6.5, 10)] and R.pairs(rows, "h1") == [(140.5, 38)]
    print("graded games: OK")

# thin data reads PENDING-style 'keep', never an adopt
res = R.evaluate(rows, R.load_live(Path(tempfile.gettempdir()) / "no_such_ncaa_live.json"))
assert all(r["decision"] == "keep" and "too few" in r["reason"] for r in res)


def season(bias, sd, n=900, seed=3):
    rnd = random.Random(seed)  # noqa: S311 - test data
    out = []
    for i in range(n):
        line, spread = rnd.uniform(125, 160), rnd.uniform(-12, 12)
        out.append({"g": str(i), "day": (date(2026, 11, 3) + timedelta(i // 15)).isoformat(),
                    "line": line, "spread": spread, "hs": 0, "as": 0, "h1": None, "ot": False,
                    "_tot": line + rnd.gauss(bias, sd), "_mar": -spread + rnd.gauss(bias, sd)})
    for r in out:
        r["hs"], r["as"] = (r["_tot"] + r["_mar"]) / 2, (r["_tot"] - r["_mar"]) / 2
    return out


live = R.load_live(Path(tempfile.gettempdir()) / "no_such_ncaa_live.json")
# a season whose misses are far wider than the fixed numbers: the refit must be adopted
wide = {r["family"]: r for r in R.evaluate(season(3.0, 25.0), live)}
assert wide["total"]["decision"] == "adopt" and wide["total"]["adopt"]["sd"] > live["total"]["sd"], wide["total"]
# a season that matches the fixed numbers: the refit must not be adopted on noise alone
same = {r["family"]: r for r in R.evaluate(season(live["total"]["bias"], live["total"]["sd"], seed=9), live)}
assert same["total"]["decision"] == "keep", same["total"]
# the holdout is the newest days only
fit_rows, hold = R.split(season(0, 10))
assert max(r["day"] for r in fit_rows) < min(r["day"] for r in hold)
print("fit and gate: OK")

# blend study: PENDING when thin, an answer when there is enough
assert bs.study(rows)["status"] == "PENDING"
rnd = random.Random(5)  # noqa: S311
big = []
for i in range(900):
    sp = rnd.uniform(-12, 12)
    m = -sp + rnd.gauss(0, 11)
    p_mkt = min(max(R.nl._phi(-sp / 11.4), 0.02), 0.98)
    big.append({"day": (date(2026, 11, 3) + timedelta(i // 15)).isoformat(), "spread": sp, "hs": 70 + max(m, 0.5),
                "as": 70 + max(-m, 0.5), "ml_home": 1 / p_mkt * 1.05, "ml_away": 1 / (1 - p_mkt) * 1.05})
st = bs.study(big)
assert st["status"] == "OK" and 0 <= st["w"] <= 1 and set(st["holdout_log_loss"]) == {"market", "model", "blend"}, st
assert "market" in bs.render(st) and "PENDING" in bs.render(bs.study(rows))
print("blend study: OK")
