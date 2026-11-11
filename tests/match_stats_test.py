"""
Offline test of the FotMob post-match stats (data/match_stats.py,
backtest/match_stats_study.py): stats parsed (counts from "369 (83%)", a
missing stat left out, never 0), only rated fixtures that finished and match
strictly, no duplicates, failures reported, and the study + team profiles.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

from data import fotmob
from data import match_stats as ms


def page(xg=True, poss=(60, 40)):
    top = [{"key": "BallPossesion", "stats": list(poss)}, {"key": "total_shots", "stats": [15, 8]},
           {"key": "ShotsOnTarget", "stats": [6, 2]}, {"key": "big_chance", "stats": [3, 1]},
           {"key": "accurate_passes", "stats": ["369 (83%)", "182 (71%)"]}, {"key": "corners", "stats": [7, 2]}]
    if xg:
        top.insert(1, {"key": "expected_goals", "stats": ["1.84", "0.62"]})
    return {"content": {"stats": {"Periods": {"All": {"stats": [
        {"key": "top_stats", "stats": top},
        {"key": "passes", "stats": [{"key": "passes", "stats": [None, None]}, {"key": "passes", "stats": [445, 257]}]},
    ]}}}}}


s = ms.parse_stats(page())
assert s["xg"] == [1.84, 0.62] and s["passes_acc"] == [369.0, 182.0] and s["passes"] == [445.0, 257.0], s
assert "xg" not in ms.parse_stats(page(xg=False)), "a stat FotMob didn't publish is absent, never 0"
print("stats parsed (counts, missing stats left out): OK")

d = Path(tempfile.mkdtemp())
ledger, store = d / "picks", d / "stats"
ledger.mkdir()
(ledger / "picks_2026-10-06.json").write_text(json.dumps({"rated": [
    {"home": "Croatia", "away": "Spain", "league": "UEFA Nations League"},
    {"home": "Albania", "away": "San Marino", "league": "UEFA Nations League"},
    {"home": "Nowhere Town", "away": "Elsewhere FC", "league": "FA Cup"}]}), encoding="utf-8")
matches = [{"id": 1, "home": "Croatia", "away": "Spain", "finished": True, "score": [1, 2]},
           {"id": 2, "home": "Albania", "away": "San Marino", "finished": False, "score": [None, None]}]
calls = []
fotmob.matches_on = lambda day: matches
fotmob.match_details = lambda mid: calls.append(mid) or page(poss=(28, 72))
n, notes = ms.collect(days=1, today=date(2026, 10, 7), folder=store, ledger_dir=ledger, pause=0)
assert n == 1 and calls == [1], "only the finished, strictly matched rated fixture"
assert any("1 of 3 rated fixtures not found" in x for x in notes), notes
assert ms.collect(days=1, today=date(2026, 10, 7), folder=store, ledger_dir=ledger, pause=0)[0] == 0, "no duplicates"
matches[1]["finished"], matches[1]["score"] = True, [2, 1]


def broken(mid):
    raise RuntimeError("down")


fotmob.match_details = broken
n, notes = ms.collect(days=1, today=date(2026, 10, 7), folder=store, ledger_dir=ledger, pause=0)
assert n == 0 and any("unavailable" in x for x in notes), "a failed page is reported, retried next run"
print("rated + finished + strict match only, no duplicates, failures reported: OK")

rows = ms.load(store)
assert rows[0]["home"] == "Croatia" and rows[0]["score"] == [1, 2] and rows[0]["stats"]["possession"] == [28.0, 72.0]
for i in range(3):                                   # three more Croatia matches for a profile
    ms.archive([{**rows[0], "fotmob_id": 100 + i}], store)
import match_stats_study as mss  # noqa: E402

ms.STATS_DIR = store
mss.OUT, mss.PROFILES = d / "study.md", store / "team_profiles.json"
_load = ms.load
mss.ms.load = lambda folder=None: _load(store)
mss.main()
txt = mss.OUT.read_text(encoding="utf-8")
assert "4 matches" in txt and "| UEFA Nations League | 4 |" in txt
assert "| possession | 4 | 100% | 0% | 0% |" in txt, "Spain had more of the ball (72%) and won every time"
assert "| expected goals | 4 | 0% | 0% | 100% |" in txt, "Croatia had more xG (1.84) and lost every time"
assert "| Spain | UEFA Nations League | 4 | 0.62 | 1.84 |" in txt or "| Croatia | UEFA Nations League | 4 | 1.84 | 0.62 |" in txt
prof = json.loads(mss.PROFILES.read_text(encoding="utf-8"))
assert prof["Croatia"]["matches"] == 4 and abs(prof["Croatia"]["finishing"] - (1 - 1.84)) < 1e-9
print("study + team profiles: OK")

# every team stat by period, the referee, and every player with his cards from the match events (#556)
det = {"general": {"homeTeam": {"id": 1}},
       "content": {"stats": {"Periods": {
           "All": {"stats": [{"key": "shots", "stats": [{"key": "shots", "stats": [None, None]},
                                                        {"key": "blocked_shots", "stats": [4, 3]},
                                                        {"key": "accurate_passes", "stats": ["325 (78%)", "257 (73%)"]}]},
                             {"key": "defense", "stats": [{"key": "matchstats.headers.tackles", "stats": [15, 23]}]}]},
           "FirstHalf": {"stats": [{"key": "shots", "stats": [{"key": "blocked_shots", "stats": [1, 2]}]}]}}},
           "matchFacts": {"infoBox": {"Referee": {"text": "A Ref", "id": 9, "country": "X"}},
                          "events": {"events": [{"type": "Card", "card": "Yellow", "time": 22, "playerId": 7},
                                                {"type": "Card", "card": "Red", "time": 80, "playerId": 7}]}},
           "playerStats": {"7": {"id": 7, "name": "P", "teamId": 1, "teamName": "H", "isGoalkeeper": False,
                                 "stats": [{"stats": {"Fouls": {"key": "fouls", "stat": {"value": 3}},
                                                      "Tackles": {"key": "matchstats.headers.tackles", "stat": {"value": 2}},
                                                      "Passes": {"key": "accurate_passes", "stat": {"value": 16, "total": 22}}}}]},
                           "8": {"id": 8, "name": "Q", "teamId": 2, "teamName": "A", "isGoalkeeper": True, "stats": []}}}}
full = ms.parse_full(det)
assert full["all"] == {"blocked_shots": [4.0, 3.0], "accurate_passes": [325.0, 257.0], "tackles": [15.0, 23.0]}, full
assert full["h1"] == {"blocked_shots": [1.0, 2.0]}
assert ms.referee(det) == {"name": "A Ref", "id": 9, "country": "X"}
pl = {p["id"]: p for p in ms.players(det, ms.home_team_id(det))}
assert pl[7]["side"] == "home" and pl[8]["side"] == "away" and pl[8]["gk"]
assert pl[7]["fouls"] == 3 and pl[7]["tackles"] == 2 and pl[7]["accurate_passes_total"] == 22
assert pl[7]["yellow"] == 1 and pl[7]["red"] == 1 and pl[7]["card_minutes"] == [22, 80]
print("every team stat by half, referee, player lines with cards: OK")

# backfill fills old lines once and is safe to run again
bf = Path(tempfile.mkdtemp())
(bf / "ms").mkdir()
(bf / "ms" / "2026-11.jsonl").write_text(json.dumps({"date": "2026-11-01", "home": "H", "away": "A", "fotmob_id": 5,
                                                     "stats": {}}) + chr(10), encoding="utf-8")
assert ms.backfill(bf / "ms", bf / "mp", pause=0, fetch=lambda fid: det) == (1, 0)
assert ms.backfill(bf / "ms", bf / "mp", pause=0, fetch=lambda fid: det) == (0, 0)
line = json.loads((bf / "ms" / "2026-11.jsonl").read_text(encoding="utf-8"))
assert line["full"]["all"]["tackles"] == [15.0, 23.0] and line["referee"]["name"] == "A Ref"
assert len((bf / "mp" / "2026-11.jsonl").read_text(encoding="utf-8").splitlines()) == 2
print("backfill: OK")

print("ALL MATCH-STATS TESTS PASSED")
