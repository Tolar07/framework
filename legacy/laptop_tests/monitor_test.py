"""Monitor tests: state rendering, score honesty, and the outcome-training path.

The monitor settles scan-only continental predictions with real results. These
tests prove the pure logic on a THROWAWAY brain — the real brain is never
touched with a synthetic score (HR35).
"""
import sys
import tempfile
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import monitor.run_monitor as mon
from brain.store import Brain

_tmp = Path(tempfile.mkdtemp())
now = datetime.datetime.now(datetime.timezone.utc)
_later = (now + datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
_sooner = (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

# --- 1. state + score honesty -----------------------------------------------
up = {"commence_time": _later, "home_team": "A", "away_team": "B",
      "completed": False, "scores": []}
live0 = {"commence_time": _sooner, "home_team": "A", "away_team": "B",
         "completed": False, "scores": []}
live1 = {"commence_time": _sooner, "home_team": "A", "away_team": "B",
         "completed": False,
         "scores": [{"position": 0, "score": "1"}, {"position": 1, "score": "1"}]}
done = {"commence_time": _sooner, "home_team": "A", "away_team": "B",
        "completed": True,
        "scores": [{"position": 0, "score": "2"}, {"position": 1, "score": "1"}]}
assert mon._status(up) == "UPCOMING" and mon._status(live0) == "LIVE"
assert mon._status(done) == "COMPLETED"
assert mon._score_of(live0) is None, "no in-play score must be None, never 0-0"
assert mon._score_of(live1) == "1-1" and mon._score_of(done) == "2-1"
assert "NO DATA" in mon._event_line(live0), "live w/o score must say NO DATA"
assert "LIVE 1-1" in mon._event_line(live1)
assert "FT 2-1" in mon._event_line(done)
print("1. state transitions + in-play score honesty: OK")

# --- 2. outcome-training path (throwaway brain) ------------------------------
b = Brain(_tmp / "t.db")
b.append_predictions([dict(run_id="r1", predicted_at="2026-08-05T07:00:00+00:00",
    league="Champions League", fixture="Fenerbahçe v Sturm Graz",
    match_date="2026-08-05", market=m, model_engine="cross", model_prob=p,
    entry_odds=None, bookmaker=None, ev=None,
    on_deploy_shortlist=0, cal_adjustment=None)
    for m, p in [("1X2_HOME", 0.56), ("1X2_DRAW", 0.28), ("1X2_AWAY", 0.16),
                 ("OVER_1_5", 0.60), ("OVER_2_5", 0.33), ("BTTS_YES", 0.35)]])
evt = {"commence_time": "2026-08-05T18:00:00Z", "home_team": "Fenerbahce",
       "away_team": "SK Sturm Graz", "completed": True,
       "scores": [{"position": 0, "score": "2"}, {"position": 1, "score": "1"}]}
assert mon._settle_predictions(b, "Champions League", evt) == 6, \
    "all 6 market rows settle"
hits = {r["market"]: r["hit"] for r in b._conn.execute(
    "SELECT market, hit FROM predictions")}
assert hits == {"1X2_HOME": 1, "1X2_DRAW": 0, "1X2_AWAY": 0,
                "OVER_1_5": 1, "OVER_2_5": 1, "BTTS_YES": 1}, hits
assert mon._settle_predictions(b, "Champions League", evt) == 0, \
    "a settled row is never overwritten"
s = b.outcome_summary("Champions League")
assert s["n"] == 6 and abs(s["hit_rate"] - 4 / 6) < 1e-9, s
print("2. outcome training path (2-1 -> 4/6 hit, idempotent): OK")

# --- 3. a prediction that does NOT match the event is never settled -----------
b2 = Brain(_tmp / "t2.db")
b2.append_predictions([dict(run_id="r1", predicted_at="2026-08-05T07:00:00+00:00",
    league="Champions League", fixture="Arsenal v Barcelona",
    match_date="2026-08-05", market="1X2_HOME", model_engine="cross",
    model_prob=0.5, entry_odds=None, bookmaker=None, ev=None,
    on_deploy_shortlist=0, cal_adjustment=None)])
n = mon._settle_predictions(b2, "Champions League", evt)
assert n == 0, "a non-matching prediction must not be settled against a wrong match"
print("3. non-matching prediction never settled (HR35): OK")

print("\n✅ ALL MONITOR TESTS PASSED")