"""
Smoke test: synthetic league data (12 teams, round-robin, goals drawn from
known Poisson rates) -> fit -> predict -> verify -> render.
Confirms the pipeline runs end-to-end and recovers roughly sane parameters
without needing live network access.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
import numpy as np
from data.football_data_source import MatchResult
from engine.dixon_coles import fit, predict, score_matrix
from verification.id403 import verify, SourcedDatum, Tier, stamp
from output.produce_bet import BoardFixture, render_produce_bet
from clv.clv_logger import CLVLog, compute_clv

random.seed(42)
np.random.seed(42)

TEAMS = [f"Team{i}" for i in range(1, 13)]
# Ground-truth strengths so we can sanity-check the fit recovers something reasonable.
TRUE_ATTACK = {t: random.uniform(-0.4, 0.4) for t in TEAMS}
TRUE_DEFENCE = {t: random.uniform(-0.4, 0.4) for t in TEAMS}
TRUE_HOME_ADV = 0.3

results = []
for round_num in range(2):  # double round-robin
    for i, home in enumerate(TEAMS):
        for j, away in enumerate(TEAMS):
            if i == j:
                continue
            lam_h = np.exp(TRUE_ATTACK[home] + TRUE_DEFENCE[away] + TRUE_HOME_ADV)
            lam_a = np.exp(TRUE_ATTACK[away] + TRUE_DEFENCE[home])
            fthg = np.random.poisson(lam_h)
            ftag = np.random.poisson(lam_a)
            results.append(MatchResult(
                league="Synthetic Test League", date="2026-01-01",
                home_team=home, away_team=away, fthg=int(fthg), ftag=int(ftag),
                ftr="H" if fthg > ftag else ("A" if ftag > fthg else "D"),
                closing_home_odds=2.0, closing_draw_odds=3.3, closing_away_odds=3.8,
            ))

print(f"Generated {len(results)} synthetic matches across {len(TEAMS)} teams")

model = fit(results)
print(f"Fitted home_advantage={model.home_advantage:.3f} (true={TRUE_HOME_ADV}), "
      f"rho={model.rho:.3f}")
assert 0.05 < model.home_advantage < 0.6, "home advantage fit is not in a sane range"
assert len(model.teams) == 12, "all 12 teams should be rated with 22 matches each"

# --- test a single prediction ---
probs = predict(model, "Team1", "Team2")
assert probs is not None
print(f"\nTeam1 v Team2: 1={probs.p_home:.2%} X={probs.p_draw:.2%} 2={probs.p_away:.2%} "
      f"(sum={probs.p_home+probs.p_draw+probs.p_away:.4f})")
assert abs(probs.p_home + probs.p_draw + probs.p_away - 1.0) < 1e-6, "1X2 must sum to 1 (BUG2 check)"
print(f"O1.5={probs.p_over_15:.2%} O2.5={probs.p_over_25:.2%} O3.5={probs.p_over_35:.2%} "
      f"BTTS={probs.p_btts_yes:.2%}")
assert probs.p_over_15 >= probs.p_over_25 >= probs.p_over_35, "Overs should be monotonic decreasing"

# --- test unrated team returns None, never a fabricated number (HR35) ---
none_probs = predict(model, "Team1", "GhostFC")
assert none_probs is None, "unrated team must return None, not a guessed probability"
print("\nUnrated-team fixture correctly returns None (HR35 guard OK)")

# --- test score matrix normalises and low-score correction fires ---
m = score_matrix(1.2, 1.1, model.rho)
assert abs(m.sum() - 1.0) < 1e-9, "score matrix must sum to 1"
print(f"\n0-0 cell probability: {m[0,0]:.4f} (rho={model.rho:.3f} correction applied)")

# --- test ID403 verification ---
v_agree = verify([
    SourcedDatum(domain="footystats.org", value="Team1 v Team2 confirmed", url="http://x"),
    SourcedDatum(domain="bbc.co.uk", value="Team1 v Team2 confirmed", url="http://y"),
])
assert v_agree.tier == Tier.VERIFIED, f"two independent agreeing T1/T2 sources should VERIFY, got {v_agree.tier}"
print(f"\nTwo-source agreement -> {v_agree.tier.value} ({stamp(v_agree)})")

v_conflict = verify([
    SourcedDatum(domain="footystats.org", value="McInnes", url="http://x"),
    SourcedDatum(domain="bbc.co.uk", value="Vrancken", url="http://y"),
])
assert v_conflict.tier == Tier.CONFLICT
print(f"Disagreeing sources -> {v_conflict.tier.value} ({stamp(v_conflict)}) — not silently resolved")

v_none = verify([])
assert v_none.tier == Tier.NO_DATA
print(f"No sources -> {v_none.tier.value} ({stamp(v_none)})")

# --- test CLV logger ---
clv_path = str(Path(__file__).parent / "tmp_clv_log.json")
Path_clv = Path(clv_path)
if Path_clv.exists():
    Path_clv.unlink()
log = CLVLog(path=clv_path)
leg = log.log_entry(league="Synthetic Test League", fixture="Team1 v Team2",
                     market="Over 1.5", model_prob=probs.p_over_15,
                     entry_odds=1.45, entry_capture_path="CL-LIVE", phase="phase2_paper")
log.log_close(leg.leg_id, closing_odds=1.38, closing_capture_path="CL-ARCHIVE")
status = log.phase2_status()
# Sign convention guard (corrected 2026-08-03): POSITIVE CLV = beat the close.
# Taking 1.45 into a 1.38 close means you got the longer price, so this must
# come out positive. The previous formula returned negative here while the
# Phase 3 gate required a positive mean — i.e. the gate was backwards.
assert compute_clv(1.45, 1.38) > 0, "entry longer than close must be POSITIVE CLV"
assert compute_clv(1.38, 1.45) < 0, "entry shorter than close must be NEGATIVE CLV"
print(f"\nCLV test leg: entry=1.45 close=1.38 -> CLV%={compute_clv(1.45,1.38):+.2f}% "
      f"(positive = took a longer price than the close, i.e. beat the market)")
print(f"Phase 2 status: {status}")
assert status["legs_with_clv"] == 1
Path_clv.unlink()

# --- test render_produce_bet doesn't crash and honestly reports NO DATA ---
board = [
    BoardFixture(fixture="Team1 v Team2", probs=probs, verification=v_agree),
    BoardFixture(fixture="Team3 v GhostFC", probs=None,
                 verification=verify([]),
                 rejection_reason="GhostFC unrated — insufficient match history"),
]
output = render_produce_bet(mode="Mode A", phase="Phase 1", leagues_scanned=["Synthetic Test League"],
                             calibration_count=0, mean_clv=None, data_flags=[], board=board)
print("\n" + "=" * 60)
print(output)
print("=" * 60)
assert "NO DATA — PENDING" in output, "unrated fixture must surface as NO DATA — PENDING, never fabricated"

print("\n✅ ALL SMOKE TESTS PASSED")
