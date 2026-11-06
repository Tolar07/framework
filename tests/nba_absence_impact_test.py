"""Offline test of engine/nba_absence_impact.py (framework #330): already-out and rotation weights,
priced-in line move, PENDING when data is missing (HR35), record-only output. No network."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_absence_impact as t

MINS = {"a": 36, "b": 30, "c": 24, "d": 20, "e": 20, "f": 20, "g": 20, "h": 20, "i": 20, "j": 10}


def rows(team, mins, missing_from=None, games=7):
    out = []
    for n in range(1, games + 1):
        for pid, m in mins.items():
            mm = 0 if (pid == "a" and missing_from and n >= missing_from) else m
            out.append({"d": f"2026-11-{n:02d}", "g": f"g{n}", "t": team, "p": pid, "n": pid.upper(), "m": mm,
                        "pts": m / 2, "s": m > 25})
    return out


OUT_A = [{"id": "a", "name": "A", "status": "Out"}]
fresh = rows("BOS", MINS)                  # A played every game: a fresh absence
r = t.team_impact(fresh, "BOS", OUT_A)
assert r["adj_share"] == r["raw_share"] and r["level"] == "CAUTION", r
assert "line move PENDING" in r["players"][0]["why"]

old = rows("BOS", MINS, missing_from=3)    # A missed the last 5 of 7: already out, priced in
r = t.team_impact(old, "BOS", OUT_A)
assert r["adj_share"] == 0.0 and r["level"] == "OK" and r["players"][0]["weight"] == 0.0, r

part = rows("BOS", MINS, missing_from=5)   # A played 3 of the last 5: rotation weight
r = t.team_impact(part, "BOS", OUT_A)
assert 0 < r["players"][0]["weight"] < 1 and r["adj_share"] < r["raw_share"], r

r = t.team_impact(fresh, "BOS", OUT_A, line_move=-1.5)
assert r["adj_share"] == 0.0 and "priced in" in r["players"][0]["why"]
r = t.team_impact(fresh, "BOS", OUT_A, line_move=0.3)
assert r["adj_share"] == r["raw_share"], "small move is not priced in"

assert t.team_impact(fresh, "BOS", None)["level"] == "PENDING"
assert t.team_impact([], "BOS", [])["adj_share"] is None

g = t.assess_game(part, "BOS", "LAL", {"BOS": OUT_A, "LAL": []})
assert g["onoff"].startswith("PENDING") and g["away"]["level"] == "PENDING"
s = t.study(rows("BOS", MINS, missing_from=4, games=12))   # 9 absences: 4 fresh-ish, last 4 already out
assert s["absences"] == 9 and s["already_out"] == 4 and s["share_already_out"] == 0.444, s
with tempfile.TemporaryDirectory() as d:
    t.record("2026-11-06", "now", "LAL@BOS", g, Path(d))
    assert (Path(d) / "2026-11-06.jsonl").read_text().count("BOS") >= 1
print("nba_absence_impact_test OK")
