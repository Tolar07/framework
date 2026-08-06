"""Engine consensus tests (ID412) — the ScoreGPT structure over OLP's three
engines: majority vote on the 1X2 result across whatever opinions exist,
averaged probabilities, and the split flag as the divergence guardrail
(extended to cover xG, which engine_divergence never did)."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.consensus import compute_consensus
from output.produce_bet import BoardFixture, render_fixture_block, render_telegram_board
from verification.id403 import VerificationResult, Tier

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_consensus_"))


def _probs(h=0.5, d=0.25, a=0.25):
    """A fake FixtureProbabilities with the fields consensus reads."""
    return SimpleNamespace(p_home=h, p_draw=d, p_away=a,
                           home_team="Home FC", away_team="Away FC",
                           p_over_15=0.7, p_over_25=0.5, p_btts_yes=0.5,
                           lambda_home=1.4, lambda_away=1.0)


# --- 1. 2-of-2 agreement -> consensus result + averaged probs ---------------
c = compute_consensus(_probs(0.55, 0.25, 0.20), (0.45, 0.30, 0.25), None)
assert c is not None and c.result == "HOME", c
assert c.n_engines == 2 and c.agreeing == 2 and not c.split, c
assert abs(c.avg_home - 0.50) < 1e-9, c          # (0.55+0.45)/2
assert abs(c.avg_away - 0.225) < 1e-9, c         # (0.20+0.25)/2
print("1. 2-of-2 agreement -> consensus HOME, averaged probs: OK")

# --- 2. 2-of-3 -> consensus, agreeing=2, split=True -------------------------
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.30, 0.35, 0.35))
assert c is not None and c.result == "HOME", c
assert c.n_engines == 3 and c.agreeing == 2 and c.split, c
print("2. 2-of-3 -> consensus HOME, one dissent flagged: OK")

# --- 3. 3-of-3 -> consensus, no split ---------------------------------------
c = compute_consensus(_probs(0.55, 0.25, 0.20), (0.45, 0.30, 0.25),
                      (0.50, 0.25, 0.25))
assert c is not None and c.result == "HOME" and c.agreeing == 3 and not c.split, c
assert abs(c.avg_draw - (0.25 + 0.30 + 0.25) / 3) < 1e-9, c
print("3. 3-of-3 -> consensus HOME, unanimous, averaged draw: OK")

# --- 4. 1-of-1 (single engine) -> None (a lone engine is not a consensus) ---
assert compute_consensus(_probs(), None, None) is None
print("4. single opinion -> None, never fabricates consensus: OK")

# --- 5. 1-1 split (no xG) -> result None, split=True ------------------------
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.10, 0.40, 0.50), None)
assert c is not None and c.result is None and c.split, c
assert c.agreeing == 1, c
print("5. 1-1 tie (no xG) -> NO CONSENSUS, split flagged: OK")

# --- 6a. 4 engines (bookmaker added, ID413): 3-of-4 = consensus, 2-2 = none --
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.20, 0.30, 0.50), (0.4828, 0.2759, 0.2413))
assert c is not None and c.result == "HOME" and c.n_engines == 4 \
    and c.agreeing == 3 and c.split, c
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.20, 0.30, 0.50), (0.20, 0.30, 0.50))
assert c is not None and c.result is None and c.n_engines == 4, c
print("6a. 4-engine vote (bookmaker): 3-of-4 consensus, 2-2 none: OK")

# --- 6. 1-1-1 -> result None -------------------------------------------------
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.20, 0.50, 0.30),
                      (0.20, 0.30, 0.50))
assert c is not None and c.result is None and c.split, c
print("6. 1-1-1 (three different picks) -> NO CONSENSUS: OK")

# --- 7. render_fixture_block shows the consensus line ------------------------
v = VerificationResult(tier=Tier.VERIFIED, value=None)
bf = BoardFixture(fixture="Home FC v Away FC (Eredivisie)", probs=_probs(),
                  verification=v, softness_tier="A",
                  elo_probs=(0.45, 0.30, 0.25),
                  consensus=compute_consensus(_probs(), (0.45, 0.30, 0.25), None))
block = render_fixture_block(bf)
assert "CONSENSUS" in block, block
assert "2 of 2 engines" in block, block

# A split renders NO CONSENSUS, never a smoothed number.
bf2 = BoardFixture(fixture="Home FC v Away FC (Eredivisie)", probs=_probs(),
                   verification=v, softness_tier="A",
                   elo_probs=(0.10, 0.40, 0.50),
                   consensus=compute_consensus(_probs(), (0.10, 0.40, 0.50), None))
assert "NO CONSENSUS" in render_fixture_block(bf2)
print("7. full board renders CONSENSUS / NO CONSENSUS: OK")

# --- 8. phone board stays lean (no consensus line) --------------------------
phone = render_telegram_board(
    mode="paper", phase="Phase 2", leagues_scanned=["Eredivisie"],
    calibration_count=0, mean_clv=None, data_flags=[], board=[bf, bf2])
assert "CONSENSUS" not in phone, phone
assert "NO CONSENSUS" not in phone, phone
print("8. phone board deliberately lean — no consensus text: OK")

# --- 9. consensus persisted to the brain as model_engine='consensus' --------
from brain.store import Brain
from run_daily import _predictions_from_board
brain = Brain(_tmp / "t.db")
n = _predictions_from_board([bf], "test-run", "2026-08-06T12:00:00Z", brain)
assert n >= 3, n
rows = brain.predictions_for(fixture="Home FC v Away FC", engine="consensus")
assert len(rows) == 3, rows
by_market = {r["market"]: r["model_prob"] for r in rows}
assert by_market["1X2_HOME"] == 0.475 and by_market["1X2_DRAW"] == 0.275, by_market
# A split with no majority is never persisted as consensus (HR35: it is not
# a prediction) — the DC + Elo rows still persist, only the consensus rows
# are absent.
bf3 = BoardFixture(fixture="Split FC v Other FC (Eredivisie)", probs=_probs(),
                   verification=v, softness_tier="A",
                   elo_probs=(0.10, 0.40, 0.50),
                   consensus=compute_consensus(_probs(), (0.10, 0.40, 0.50), None))
n2 = _predictions_from_board([bf3], "test-run", "2026-08-06T12:00:00Z", brain)
assert n2 == 9, f"split fixture keeps DC+Elo rows (9), got {n2}"
split_rows = brain.predictions_for(fixture="Split FC v Other FC", engine="consensus")
assert not split_rows, f"no-majority split must persist no consensus rows, got {split_rows}"
print("9. consensus persisted to brain; no-majority split persists no consensus: OK")

print("\n✅ ENGINE CONSENSUS WORKS — majority vote, averaged 1X2, split guardrail,"
      " brain persistence.")
