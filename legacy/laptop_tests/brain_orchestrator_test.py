"""Brain <-> orchestrator integration: DC/Elo reuse is provably identical,
mutation invalidates the cache, and fit_cross_league(pool=) is behaviour-
preserving (the double build_pool regression can never return silently).

Mocks the network sources the same way multi_league_test does; never touches
the real brain/olp.db.
"""
import sys
import tempfile
import copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

import orchestrator
from data.football_data_source import MatchResult
from brain.store import Brain

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_brain_orch_test_"))


def _synthetic_results(n=120, seed=7):
    import random
    random.seed(seed)
    teams = ["AA", "BB", "CC", "DD", "EE", "FF", "GG", "HH"]
    rs = []
    for i in range(n):
        h = teams[i % 8]
        a = teams[(i + 1) % 8]
        fh, fa = random.randint(0, 3), random.randint(0, 3)
        rs.append(MatchResult(league="AA League",
                              date=f"2026-07-{1 + i % 28:02d}",
                              home_team=h, away_team=a, fthg=fh, ftag=fa,
                              ftr="H" if fh > fa else "A" if fa > fh else "D"))
    rs.sort(key=lambda r: r.date)
    return rs


# --- 1. DC reuse is provably identical + mutation invalidates ---------------
results = _synthetic_results()
brain = Brain(_tmp / "o1.db")

st1 = {}
with patch("orchestrator.load_league", return_value=(results, [])):
    b1, _ = orchestrator.scan_one_league("AA League", "2526",
                                         upcoming_fixtures=[("AA", "BB")],
                                         brain=brain, stats=st1)
assert st1["dc_refit"] and not st1.get("dc_reused"), "first run must refit"
assert st1["elo_seeded"] is False, "first run cold Elo"

st2 = {}
with patch("orchestrator.load_league", return_value=(results, [])):
    b2, _ = orchestrator.scan_one_league("AA League", "2526",
                                         upcoming_fixtures=[("AA", "BB")],
                                         brain=brain, stats=st2)
assert st2["dc_reused"] and not st2.get("dc_refit"), "identical history reuses"
assert st2["elo_seeded"] is True, "second run seeds Elo incrementally"
p1, p2 = b1[0].probs, b2[0].probs
assert (p1.p_home, p1.p_draw, p1.p_away) == (p2.p_home, p2.p_draw, p2.p_away)
assert abs(p1.p_over_25 - p2.p_over_25) < 1e-12, \
    "reuse must be byte-identical, not close"
assert b2[0].model_engine == "dc"

# mutate ONE result -> refit, never a stale reuse
mut = copy.deepcopy(results)
m = copy.deepcopy(mut[0]); m.fthg = 9; m.ftag = 0; m.ftr = "H"; mut[0] = m
st3 = {}
with patch("orchestrator.load_league", return_value=(mut, [])):
    b3, _ = orchestrator.scan_one_league("AA League", "2526",
                                         upcoming_fixtures=[("AA", "BB")],
                                         brain=brain, stats=st3)
assert st3["dc_refit"] and not st3.get("dc_reused"), \
    "a changed row must invalidate the cache"
print("1. DC reuse provably identical + mutation invalidates: OK")

# --- 2. fit_cross_league(pool=) is behaviour-preserving ---------------------
from engine import cross_league as xleague
from data.football_data_source import MatchResult as MR

def _pool(n=240):
    import random
    random.seed(3)
    teams = ["A%d" % i for i in range(12)]
    rs = []
    for i in range(n):
        h, a = teams[i % 12], teams[(i + 3) % 12]
        fh, fa = random.randint(0, 3), random.randint(0, 3)
        rs.append(MR(league="UCL", date=f"2026-03-{1 + i % 28:02d}",
                     home_team=h, away_team=a, fthg=fh, ftag=fa,
                     ftr="H" if fh > fa else "A" if fa > fh else "D"))
    return rs

pooled = _pool()
info = {"weakly_anchored": []}
# both paths must fit the SAME data -> same parameters
with patch("engine.cross_league.build_pool", return_value=(pooled, info, [])):
    m_no_pool, _, _ = xleague.fit_cross_league("Champions League")
m_with_pool, _, _ = xleague.fit_cross_league("Champions League",
                                             pool=(pooled, info))
assert m_no_pool is not None and m_with_pool is not None
assert m_no_pool.league == m_with_pool.league == "Champions League"
assert abs(m_no_pool.home_advantage - m_with_pool.home_advantage) < 1e-9
assert abs(m_no_pool.rho - m_with_pool.rho) < 1e-9
assert m_no_pool.n_matches_fit == m_with_pool.n_matches_fit
assert set(m_no_pool.teams) == set(m_with_pool.teams)
print("2. fit_cross_league(pool=) behaviour-preserving: OK")

# --- 3. cross-league path: reuse + pool_built once --------------------------
brain2 = Brain(_tmp / "o2.db")
st4 = {}
with patch("engine.cross_league.build_pool", return_value=(pooled, info, [])):
    b4, _ = orchestrator.scan_one_league(
        "Champions League", "2526", upcoming_fixtures=[("A0", "A3")],
        brain=brain2, stats=st4)
assert st4.get("dc_refit") and st4.get("pool_built"), \
    "first cross scan must build the pool and refit"
assert b4[0].model_engine == "cross"
st5 = {}
with patch("engine.cross_league.build_pool", return_value=(pooled, info, [])):
    b5, _ = orchestrator.scan_one_league(
        "Champions League", "2526", upcoming_fixtures=[("A0", "A3")],
        brain=brain2, stats=st5)
assert st5.get("dc_reused") and st5.get("pool_built") and not st5.get("dc_refit"), \
    "identical pool must reuse the cached cross fit"
p4, p5 = b4[0].probs, b5[0].probs
assert (p4.p_home, p4.p_draw, p4.p_away) == (p5.p_home, p5.p_draw, p5.p_away)
print("3. cross-league reuse + single pool build: OK")

print("\n✅ ALL BRAIN/ORCHESTRATOR TESTS PASSED")
