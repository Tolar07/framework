"""
Offline test of the match study and tactical matchup layer
(data/match_study.py, engine/tactics.py, engine/tactics_study.py): a FotMob
match page parsed into formations, shot situations, press / line proxies and
game state; profiles never see a match at or after `as_of`; the matchup read
prices markets from a scoreline grid and names the clash; the board's chance
moves only by the fitted weight, capped; a lesson is proven only on matches
it had not seen; another market is flagged only from another family.
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import match_study as ms
from engine import tactics as tx
from engine import tactics_study as ts


def page():
    stats = [
        {"key": "top_stats", "stats": [{"key": "BallPossesion", "stats": [62, 38]},
                                       {"key": "expected_goals", "stats": ["1.19", "1.94"]},
                                       {"key": "corners", "stats": [6, 6]}]},
        {"key": "passes", "stats": [{"key": "own_half_passes", "stats": [220, 226]},
                                    {"key": "opposition_half_passes", "stats": [349, 94]},
                                    {"key": "Offsides", "stats": [3, 1]}]},
        {"key": "defense", "stats": [{"key": "matchstats.headers.tackles", "stats": [16, 23]},
                                     {"key": "interceptions", "stats": [7, 14]}]},
        {"key": "discipline", "stats": [{"key": "fouls", "stats": [15, 11]}]},
    ]
    shots = [{"teamId": 1, "expectedGoals": 0.3, "situation": "RegularPlay", "min": 10, "shotType": "RightFoot"},
             {"teamId": 2, "expectedGoals": 0.6, "situation": "FastBreak", "min": 40, "shotType": "LeftFoot"},
             {"teamId": 2, "expectedGoals": 0.2, "situation": "FromCorner", "min": 70, "shotType": "Header"},
             {"teamId": 1, "expectedGoals": 0.5, "situation": "RegularPlay", "min": 80, "shotType": "LeftFoot"}]
    events = [{"type": "Goal", "time": 41, "isHome": False}, {"type": "Goal", "time": 61, "isHome": True},
              {"type": "Goal", "time": 87, "isHome": False},
              {"type": "Card", "card": "Red", "time": 30, "isHome": True}]
    return {"general": {"matchId": 9, "parentLeagueId": 87, "leagueName": "LaLiga",
                        "matchTimeUTCDate": "2026-10-25T20:00:00Z"},
            "header": {"teams": [{"id": 1, "name": "Barcelona", "score": 1}, {"id": 2, "name": "Real Madrid", "score": 2}]},
            "content": {"stats": {"Periods": {"All": {"stats": stats}}}, "shotmap": {"shots": shots},
                        "matchFacts": {"events": {"events": events}},
                        "lineup": {"homeTeam": {"id": 1, "formation": "4-2-3-1", "coach": {"name": "A"}},
                                   "awayTeam": {"id": 2, "formation": "4-4-2", "coach": {"name": "B"}}}}}


r = ms.parse_match(page())
h, a = r["home"], r["away"]
assert (h["formation"], a["formation"], h["coach"]) == ("4-2-3-1", "4-4-2", "A"), r
assert a["shot_types"]["xg"]["counter"] == 0.6 and a["shot_types"]["xg"]["set_piece"] == 0.2
assert a["shot_types"]["xg"]["header"] == 0.2 and h["shot_types"]["xg"]["open"] == 0.8
assert h["field_tilt"] == round(349 / (349 + 94), 3)
assert h["ppda_proxy"] == round(226 / (16 + 7 + 15), 2), h["ppda_proxy"]
assert h["opp_offsides"] == 1 and h["reds"] == [30]
assert h["state"]["trailing"]["min"] == 23.0 and h["state"]["level"]["min"] == 67.0, h["state"]
assert a["state"]["level"]["xg_for"] == 0.8 and a["state"]["level"]["xg_against"] == 0.8 and a["state"]["leading"]["xg_against"] == 0.0
assert ms.parse_match({"header": {"teams": []}}) is None, "no score -> no half-read row"
print("match page parsed (formation, situations, press/line proxies, game state): OK")


def league(n_weeks=14, seed=3, start="2026-08-10"):
    """8 teams; team 1 counters hard, team 2 plays a high line, others plain."""
    rnd = random.Random(seed)
    rows, t0 = [], datetime.fromisoformat(start)
    ids = list(range(1, 9))
    for w in range(n_weeks):
        rnd.shuffle(ids)
        for k in range(0, 8, 2):
            hid, aid = ids[k], ids[k + 1]

            def side(tid, oid):
                counter = 0.7 if tid == 1 else 0.1
                xg = 1.2 + counter + (0.4 if oid == 2 and tid == 1 else 0) + rnd.uniform(-0.3, 0.3)
                return {"id": tid, "name": f"Team {tid}", "formation": "4-3-3" if tid % 2 else "4-4-2",
                        "goals": int(xg + rnd.random()), "xg": round(xg, 2),
                        "shot_types": {"xg": {"open": xg - counter, "counter": counter, "set_piece": 0.2,
                                              "penalty": 0.0, "header": 0.1}},
                        "possession": 60.0 if tid == 2 else 48.0, "field_tilt": 0.5,
                        "ppda_proxy": 6.0 if tid == 2 else 10.0, "opp_offsides": 4.0 if tid == 2 else 1.0,
                        "corners": 5.0, "reds": [],
                        "state": {s: {"min": 30.0, "xg_for": 0.4, "xg_against": 0.4}
                                  for s in ("level", "leading", "trailing")}}
            hs, as_ = side(hid, aid), side(aid, hid)
            ko = (t0 + timedelta(days=7 * w, hours=k)).isoformat()[:16]
            rows.append({"fotmob_id": f"{w}-{k}", "league_id": 87, "ko": ko, "home": hs, "away": as_})
            hs["xg"], as_["xg"] = hs["xg"], as_["xg"]
    for row in rows:      # the opponent's xG is what each side conceded
        row["home"]["opp_offsides"] = row["away"]["opp_offsides"] if False else row["home"]["opp_offsides"]
    return rows


rows = league()
cut = datetime.fromisoformat("2026-09-14")
db = tx.build_profiles(rows, as_of=cut)
assert all(t["last_ko"] < "2026-09-14" for t in db["teams"].values()), "profiles saw the future"
t1, t2 = db["teams"]["1"], db["teams"]["2"]
assert t1["style"]["counter"] == "counter threat" and t2["style"]["line"] == "high line", (t1["style"], t2["style"])
rd = tx.read(t1, t2, db, 0.0, effects={})
assert "counter side v high line" in rd["tags_home"], rd
assert abs(sum(rd["probs"][k] for k in ("home", "draw", "away")) - 1) < 0.01
assert 0 < rd["probs"]["btts"] < 1 and rd["probs"]["over15"] > rd["probs"]["over25"] > rd["probs"]["over35"]
assert "counter side v high line" in rd["say"]
assert tx.read(t1, t2, db, None, effects={}) is None, "cross-league gap unknown -> no read"
print("profiles walk-forward safe; matchup read names the clash and prices the goals markets: OK")

assert tx.adjustment(0.70, 0.90, 0.0) == 0.0, "weight 0 = label only"
assert tx.adjustment(0.70, 0.90, 0.5) == 0.05, "capped at +5 pts"
assert tx.adjustment(0.70, 0.66, 0.5) == -0.02
assert tx.adjustment(0.70, None, 0.5) == 0.0
print("board chance moves by the fitted weight, capped at ±5 pts: OK")

eff = {"counter side v high line": 0.25}
rd2 = tx.read(t1, t2, db, 0.0, effects=eff)
assert abs(rd2["xg_home"] - rd["xg_home"] - 0.25) < 1e-6 and rd2["lesson_adj"][0] == 0.25
print("a proven lesson moves the attacking side's expected goals: OK")

# lessons: written from matches before the day, proven only on later ones
preds = ts.walk_forward(rows, "2026-08-31", effects={})
book = ts.update_lessons(preds, "2026-09-21", {"lessons": {}})
lessons = book["lessons"]
assert all(x["status"] == "candidate" for x in lessons.values())
tag = "counter side v high line"
if tag in lessons:
    assert lessons[tag]["written_at"] == "2026-09-21"
book = ts.update_lessons(preds, "2026-11-30", book)
for x in book["lessons"].values():
    if x["status"] == "proven":
        assert x["test_n"] >= ts.MIN_SIDES and abs(x["effect"]) <= ts.EFFECT_CAP
        assert (x["test_effect"] > 0) == (x["train_effect"] > 0)
print("lessons: candidates written as of a day, proven only on unseen matches: OK")

w = ts.fit_weight(preds[:10])
assert w["weight"] == 0.0 and "label only" in w["why"]
print("weight stays 0 (label only) without 40 priced matches: OK")

# better market: another family only, priced above the matchup's fair odds
from engine import full_markets as fm  # noqa: E402


class Q:
    def __init__(self, price):
        self.price = price


g = tx.grid(1.8, 1.6)
rules = {"SB:29||Yes": fm.rule_for(29, "", "Yes"), "SB:10||Home or Away": fm.rule_for(10, "", "Home or Away"),
         "SB:18|total=1.5|Over 1.5": fm.rule_for(18, "total=1.5", "Over 1.5")}
assert all(rules.values()), rules
cands = [(0.75, 0.0, "SB:10||Home or Away", 0, 0, Q(1.25)), (0.73, 0.0, "SB:29||Yes", 0, 0, Q(1.72)),
         (0.80, 0.0, "SB:18|total=1.5|Over 1.5", 0, 0, Q(1.22))]
fam = lambda k: k.split("|")[0]  # noqa: E731
note = tx.better_market("SB:10||Home or Away", 0.70, cands, g, rules, fam)
assert note and "fits the matchup better" in note, note
assert tx.better_market("SB:29||Yes", 0.73, [cands[1]], g, rules, fam) is None, "same market never flagged"
assert tx.better_market("SB:29||Yes", 0.70, [c for c in cands if c[2] != "SB:29||Yes"] + [(0.9, 0, "SB:10||Home or Away", 0, 0, Q(1.9))], g, rules, fam) is None, "only goals markets are flagged"
rules["SB:18|total=4.5|Under 4.5"] = fm.rule_for(18, "total=4.5", "Under 4.5")
assert rules["SB:18|total=4.5|Under 4.5"]
_under = [(0.74, 0.0, "SB:18|total=4.5|Under 4.5", 0, 0, Q(2.00))]
assert tx.better_market("SB:10||Home or Away", 0.70, _under, g, rules, fam) is None, \
    "an Under is never suggested, however well priced (order 12)"
print("better-market flag: another family, above the matchup's fair odds, never an Under: OK")

ex = ts.explain(preds[-1])
assert ex["why"] and ex["btts_call"] in ("right", "wrong") and "say" in ex["expected"]
print("per-match study: expected v happened v why: OK")
print("tactics_test: ALL OK")
