"""engine/player_model.py, monitor/players_run.py, backtest/player_study.py (framework #557). Offline, no network."""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import player_study  # noqa: E402
from engine import player_model as pm  # noqa: E402
from monitor import players_run as pr  # noqa: E402


def line(day, fid, side, pid, yellow=0, fouls=1, tackles=2, shots=1, sot=0, mins=90, gk=False):
    r = {"date": day, "fotmob_id": fid, "side": side, "team": side, "home": "Arsenal", "away": "Brighton", "league": "L",
         "id": pid, "name": f"P{pid}", "gk": gk, "minutes_played": mins, "fouls_committed": fouls,
         "tackles_won": tackles, "total_shots": shots, "ShotsOnTarget": sot}
    if yellow:
        r["yellow"] = yellow
    return r


rows = []
for d in range(1, 21):
    day = f"2026-10-{d:02d}"
    for side, base in (("home", 0), ("away", 100)):
        for k in range(11):
            pid = base + k
            rows.append(line(day, d, side, pid, yellow=1 if (k == 3 and d % 2 == 0) else 0,
                             fouls=3 if k == 3 else 1, shots=3 if k == 9 else 1, sot=2 if k == 9 else 0, gk=(k == 0)))
rows = [{**r, "_min": 90.0} for r in rows]

# 1. history is read with minutes only, and a missing stat is absent, not zero (HR35)
assert pm.stat_of({"minutes_played": 90}, "fouls") is None
assert pm.stat_of({"minutes_played": 90}, "cards") == 0.0
print("missing stat stays absent: OK")

m = pm.PlayerModel.fit(rows)
xi = [{"id": k, "name": f"P{k}", "gk": k == 0} for k in range(11)]
tt = {"yellow": 2.0, "fouls": 11.0, "tackles": 15.0, "shots": 12.0, "sot": 4.0}

# 2. the players add up to the team totals (times the starters' share), the cards to the referee-scaled total
p = m.predict_side(xi, tt, xg=1.6, ref_cards=1.0)
assert not p["pending"], p["pending"]
for ev, tev in pm.TEAM_EVENT.items():
    got = sum(o["events"][ev] for o in p["players"])
    want = tt[tev] * m.xi_share[ev]
    assert abs(got - want) < 0.002, (ev, got, want)       # outputs are rounded to 4 places
p2 = m.predict_side(xi, tt, xg=1.6, ref_cards=1.2)
assert abs(sum(o["events"]["cards"] for o in p2["players"]) - 1.2 * sum(o["events"]["cards"] for o in p["players"])) < 0.002
print("player numbers add up to the team model: OK")

# 3. the card-prone, foul-prone and shot-taking players come out on top; the scorer chances agree with the team xG
by = {o["id"]: o["events"] for o in p["players"]}
assert by[3]["card_chance"] == max(e["card_chance"] for e in by.values())
assert by[3]["fouls"] > by[5]["fouls"] and by[9]["sot"] > by[5]["sot"]
assert 0 < by[9]["scorer_chance"] < 1
# anytime-scorer chances over the XI add up to about the chance of goals: sum of -ln(1-p) == xG
assert abs(sum(-math.log(1 - e["scorer_chance"]) for e in by.values()) - 1.6) < 0.01
print("ranking and scorer chances consistent with xG: OK")

# 4. a stranger gets his position group's rate, never a crash; no team total reads PENDING
q = m.predict_side([{"id": 999, "name": "New"}] + xi[1:], tt)
assert "fouls" in q["players"][0]["events"] and q["players"][0]["matches_behind"] == 0
assert m.predict_side(xi, {})["pending"] == list(pm.EVENTS)
print("unknown player and missing totals: OK")

# 5. walk-forward: fit(before=day) never sees that day
early = pm.PlayerModel.fit(rows, before="2026-10-05")
assert all(len(v["starts"]) <= 4 for v in early.players.values())
print("fit(before=...) uses earlier days only: OK")

# 6. referee strictness: shrunk to 1, above 1 for a strict one
mrows = [{"date": f"2026-10-{d:02d}", "league": "L", "stats": {"yellow": [3, 2]},
          "referee": {"name": "Strict" if d <= 10 else "Mild"}} for d in range(1, 21)]
for r in mrows[:10]:
    r["stats"]["yellow"] = [5, 4]
assert pm.referee_factor(mrows, "Strict", "L") > 1.0 > pm.referee_factor(mrows, "Mild", "L")
assert pm.referee_factor(mrows, None, "L") == 1.0 and pm.referee_factor(mrows, "Unknown", "L") == 1.0
print("referee factor: OK")

# 7. the study reads PENDING with too little data and writes no published stat
with tempfile.TemporaryDirectory() as d:
    pd = Path(d) / "players"
    pd.mkdir()
    (pd / "2026-10.jsonl").write_text("\n".join(json.dumps({k: v for k, v in r.items() if k != "_min"})
                                                for r in rows), encoding="utf-8")
    res = player_study.run(pd, Path(d) / "none")
    assert res["pending"] and res["lines"] == len(rows)
    text, publish = player_study.report(res)
    assert "PENDING" in text and publish == [] and "PLAYER_PUBLISH = []" in text
print("study PENDING without enough data: OK")

# 7b. the walk-forward path runs end to end on synthetic data (thresholds lowered) and reports every event
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "p").mkdir()
    (d / "s").mkdir()
    (d / "p" / "2026-10.jsonl").write_text(chr(10).join(json.dumps({k: v for k, v in r.items() if k != "_min"})
                                                    for r in rows), encoding="utf-8")
    ms_rows = [{"date": f"2026-10-{n:02d}", "fotmob_id": n, "league": "L", "home": "A", "away": "B",
                "full": {"all": {"tackles": [15, 15]}},
                "stats": {"yellow": [1, 0], "fouls": [11, 11], "shots": [12, 12], "sot": [4, 4],
                          "xg": [1.5, 1.0]}} for n in range(1, 21)]
    (d / "s" / "2026-10.jsonl").write_text(chr(10).join(json.dumps(r) for r in ms_rows), encoding="utf-8")
    player_study.PLAYER_MIN_DAYS, player_study.PLAYER_MIN_LINES, player_study.WARMUP_DAYS = 5, 10, 5
    res = player_study.run(d / "p", d / "s")
    assert not res["pending"] and set(res["events"]) == set(pm.EVENTS), res["events"].keys()
    assert res["events"]["cards"]["n"] > 100 and res["events"]["cards"]["brier_model"] is not None
    text, publish = player_study.report(res)
    assert "Calibration" in text and "PLAYER_PUBLISH" in text
print("study end to end (synthetic): OK")

# 8. the runner: a published-nothing day carries no numbers, a side without a line-up reads PENDING, grading works
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    pr.PICKS, pr.EVENTS, pr.OUT = d / "picks", d / "events", d / "players"
    for x in (pr.PICKS, pr.EVENTS, pr.OUT):
        x.mkdir()
    day = "2026-10-25"
    (pr.PICKS / f"picks_{day}.json").write_text(json.dumps({"rated": [{"home": "Arsenal", "away": "Brighton", "league": "L"}]}))
    ev = {"home": 1.0, "away": 1.0}
    (pr.EVENTS / f"events_{day}.json").write_text(json.dumps({"games": [{"home": "Arsenal", "away": "Brighton", "league": "L",
        "events": {k: dict(ev) for k in pm.TEAM_EVENT.values()}}]}))
    page = {"content": {"lineup": {"lineupType": "predicted",
            "homeTeam": {"starters": [{"id": k, "name": f"P{k}"} for k in range(11)]}, "awayTeam": {"starters": []}}}}
    fetch = (lambda day: [{"id": 1, "home": "Arsenal", "away": "Brighton"}], lambda i: page,
             lambda lst, h, a: lst[0])
    doc = pr.predict_day(day, m, [], [], fetch)
    g = doc["games"][0]
    assert doc["label"] == "shadow" and g["home_side"]["players"][0]["events"] == {}, "nothing published: no numbers"
    assert g["away_side"]["pending"] == "no predicted XI"
    doc = pr.predict_day(day, m, [], ["cards", "sot"], fetch)
    assert "card_chance" in doc["games"][0]["home_side"]["players"][3]["events"]
    (pr.OUT / f"players_{day}.json").write_text(json.dumps(doc))
    played = [{**r, "date": day, "fotmob_id": 7, "home": "Arsenal", "away": "Brighton"} for r in rows if r["fotmob_id"] == 2]
    gr = pr.grade(played, "2026-10-26")
    assert gr["games"] == 1 and gr["players"] == 11 and gr["card_brier"] is not None, gr
print("runner and grading: OK")
print("ALL OK")
