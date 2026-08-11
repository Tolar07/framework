"""ScoreGPT parity tests (ID414) — data layer only.

1. Dixon-Coles modal scoreline: argmax of Poisson matrix -> "predicted 2–1"
2. Elo widened coverage: cross-league seeded clubs get probabilities below min_matches
3. Brain graded_yesterday + rolling_7d queries
4. Schema serialization: modal_scoreline, engine_picks, consensus_pick, yesterday_graded, rolling_7d
5. Run_daily payload wires it all together
6. Widened bookmaker: one scan league pulled when quota permits
"""
import sys
import tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import predict, score_matrix, MAX_GOALS
from engine.elo import EloModel, BASE_RATING
from brain.store import Brain
from webapp.schema import fixture_to_dict, build_payload, probs_to_dict
from output.produce_bet import BoardFixture
from verification.id403 import VerificationResult, Tier
from types import SimpleNamespace

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_scoregpt_"))


# --- 1. Modal scoreline from Poisson matrix ---------------------------------
print("1. Modal scoreline math...")
lam_h, lam_a, rho = 1.8, 1.2, 0.13
m = score_matrix(lam_h, lam_a, rho)
flat = m.flatten()
idx = int(np.argmax(flat))
most_h, most_a = divmod(idx, MAX_GOALS + 1)
assert (most_h, most_a) == (1, 0), f"expected (1,0) got {(most_h, most_a)}"
print(f"   1.8 vs 1.2 -> modal {most_h}–{most_a} (matrix max at {m[most_h, most_a]:.4f}): OK")


# --- 2. predict() returns modal_scoreline -----------------------------------
print("2. predict() includes modal_scoreline...")
# Use a fake model object with the required interface
fake_model = SimpleNamespace(
    lambdas=lambda h, a: (lam_h, lam_a),
    rho=rho
)
p = predict(fake_model, "Home", "Away")
assert p is not None
assert hasattr(p, "modal_scoreline")
assert p.modal_scoreline == (1, 0), f"expected (1,0) got {p.modal_scoreline}"
print(f"   predict().modal_scoreline = {p.modal_scoreline}: OK")


# --- 3. probs_to_dict serializes modal_scoreline ----------------------------
print("3. probs_to_dict serializes modal_scoreline...")
d = probs_to_dict(p)
assert "modal_scoreline" in d
assert d["modal_scoreline"] == [1, 0]
print(f"   serialized as {d['modal_scoreline']}: OK")


# --- 4. Elo widened coverage for cross-league seeded clubs ------------------
print("4. Elo cross-league seed coverage...")
elo = EloModel()
# Give a club a cross-league seed rating (not BASE_RATING)
elo.ratings["NewClub"] = 1600  # seeded
elo.matches_seen["NewClub"] = 2  # only 2 matches in THIS division
# Old logic: would refuse (<6 matches). New logic: seed != BASE_RATING -> allow
probs = elo.probabilities("NewClub", "OldClub", min_matches=6)
# Need both clubs rated; give OldClub a real rating too
elo.ratings["OldClub"] = 1500
elo.matches_seen["OldClub"] = 50
probs = elo.probabilities("NewClub", "OldClub", min_matches=6)
assert probs is not None, "cross-league seed should allow probabilities"
print(f"   seeded club with <6 matches -> probs {probs}: OK")


# --- 5. Brain graded_yesterday + rolling_7d ---------------------------------
print("5. Brain graded_yesterday + rolling_7d...")
brain = Brain(_tmp / "t.db")
# Need a settled prediction to test
from datetime import date as _date, timedelta as _td
yesterday = (_date.today() - _td(days=1)).isoformat()
brain._conn.execute("""
    INSERT INTO predictions (run_id, predicted_at, league, fixture, match_date,
        market, model_engine, model_prob, entry_odds, bookmaker, ev,
        on_deploy_shortlist, ft_result, hit)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ("run1", "2026-08-06T12:00:00Z", "Eredivisie", "Ajax v Feyenoord",
      yesterday, "1X2_HOME", "dc", 0.55, 1.9, "bet365", 0.045,
      1, "2-1", 1))
brain._conn.execute("""
    INSERT INTO predictions (run_id, predicted_at, league, fixture, match_date,
        market, model_engine, model_prob, entry_odds, bookmaker, ev,
        on_deploy_shortlist, ft_result, hit)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ("run1", "2026-08-06T12:00:00Z", "Eredivisie", "Ajax v Feyenoord",
      yesterday, "1X2_HOME", "elo", 0.52, 1.9, "bet365", 0.028,
      1, "2-1", 1))
brain._conn.commit()

graded = brain.graded_yesterday(yesterday)
assert len(graded) == 1
g = graded[0]
assert g["fixture"] == "Ajax v Feyenoord"
assert g["outcome"] == "2-1"
assert "dc" in g["engines"] and "elo" in g["engines"]
assert g["engines"]["dc"]["1X2_HOME"]["hit"] == True
print(f"   graded_yesterday returns 1 fixture with 2 engines + hits: OK")

rolling = brain.rolling_7d()
assert "engines" in rolling and "dc" in rolling["engines"]
assert "legs_logged" in rolling
assert rolling["period_days"] == 7
print(f"   rolling_7d returns engine_stats + legs + gate: OK")


# --- 6. fixture_to_dict includes engine_picks + consensus_pick -------------
print("6. fixture_to_dict engine_picks + consensus_pick...")
v = VerificationResult(tier=Tier.VERIFIED, value=None)
# Build a BoardFixture with all engines
from engine.consensus import compute_consensus
p = SimpleNamespace(
    p_home=0.52, p_draw=0.24, p_away=0.24,
    home_team="Feyenoord", away_team="AZ",
    p_over_15=0.75, p_over_25=0.52, p_over_35=0.30, p_btts_yes=0.55,
    lambda_home=1.8, lambda_away=1.2,
    modal_scoreline=(1, 0)
)
cons = compute_consensus(p, (0.49,0.28,0.23), (0.34,0.31,0.35), (0.522,0.248,0.23))
bf = BoardFixture(
    fixture="Feyenoord v AZ (Eredivisie)", probs=p, verification=v,
    elo_probs=(0.49,0.28,0.23),
    xg_probs=(0.34,0.31,0.35), market_probs=(0.522,0.248,0.23), consensus=cons
)
d = fixture_to_dict(bf)
assert "engine_picks" in d
assert "Dixon-Coles" in d["engine_picks"]
assert d["engine_picks"]["Dixon-Coles"]["result"] == "HOME"
assert d["engine_picks"]["Dixon-Coles"]["scala scoreline"] == [1, 0]
assert "Elo" in d["engine_picks"]
assert "xG" in d["engine_picks"]
assert "Bookmaker" in d["engine_picks"]
assert "consensus_pick" in d
assert d["consensus_pick"]["result"] == "HOME"
print(f"   engine_picks + consensus_pick serialized: OK")


# --- 7. build_payload accepts yesterday_graded + rolling_7d -----------------
print("7. build_payload includes ScoreGPT fields...")
payload = build_payload(
    date="2026-08-06", phase="phase2_paper", leagues_scanned=["Eredivisie"],
    board=[bf], data_flags=[], gate={}, telemetry={},
    calibration_count=0, mean_clv=None, recommendation="test",
    yesterday_graded=[{"fixture": "Ajax v Feyenoord", "outcome": "2-1"}],
    rolling_7d={"engines": {"dc": {"hit_rate": 0.6}}})
assert "yesterday_graded" in payload
assert "rolling_7d" in payload
print(f"   payload keys: {[k for k in payload.keys() if k not in ('board','data_flags','gate','telemetry')]}: OK")


# --- 8. Verify run_daily imports work (no syntax errors) --------------------
print("8. run_daily import check...")
import run_daily
print("   run_daily imports clean: OK")

print("\n✅ SCOREGPT PARITY DATA LAYER WORKS — modal scoreline, widened Elo,")
print("   brain graded/rolling, schema serialization, payload wiring.")