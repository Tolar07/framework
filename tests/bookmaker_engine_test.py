"""Bookmaker engine tests (ID413) — the market's devigged implied 1X2 as an
equal fourth voter in the cross-engine consensus. Real money, not a model:
it is the sharpest single calibration source in football, so the consensus
leans toward it and model-vs-market divergence becomes the strongest warning."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import markets as mkt
from engine.consensus import compute_consensus
from output.produce_bet import BoardFixture, render_fixture_block
from verification.id403 import VerificationResult, Tier

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_bookmaker_"))


def _odds(h=2.10, d=3.40, a=3.60):
    """A FixtureOdds-shaped object with real 1X2 prices."""
    return SimpleNamespace(
        home=SimpleNamespace(price=h, bookmaker="bet365", n_books=12),
        draw=SimpleNamespace(price=d, bookmaker="bet365", n_books=11),
        away=SimpleNamespace(price=a, bookmaker="bet365", n_books=13),
    )


def _probs(h=0.5, d=0.25, a=0.25):
    return SimpleNamespace(p_home=h, p_draw=d, p_away=a,
                           home_team="Home FC", away_team="Away FC",
                           p_over_15=0.7, p_over_25=0.5, p_btts_yes=0.5,
                           lambda_home=1.4, lambda_away=1.0)


# --- 1. proportional devig math: implied probs sum to exactly 1 -------------
mp = mkt.implied_1x2(_odds(h=2.0, d=3.5, a=4.0))
assert mp is not None
assert abs(sum(mp) - 1.0) < 1e-9, mp
# 1/2.0=0.50, 1/3.5≈0.2857, 1/4.0=0.25; sum≈1.0357; normalized:
assert abs(mp[0] - 0.50 / 1.035714) < 1e-6, mp   # home ~0.4828
assert abs(mp[1] - 0.285714 / 1.035714) < 1e-6, mp  # draw ~0.2759
print("1. proportional devig: probs sum to 1, margin removed: OK")

# --- 2. missing price -> None (HR35: a two-price '1X2' would fabricate) ----
assert mkt.implied_1x2(_odds(d=None)) is None
assert mkt.implied_1x2(_odds(a=None)) is None
assert mkt.implied_1x2(None) is None
assert mkt.implied_1x2(_odds(h=1.0)) is None  # degenerate odds refused
print("2. missing/degenerate price -> None, never fabricates: OK")

# --- 3. the bookmaker is an EQUAL 4TH VOTE ----------------------------------
# DC home, Elo home, xG away, bookmaker home -> 3-of-4 HOME, one dissent.
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.20, 0.30, 0.50),
                      mkt.implied_1x2(_odds(h=2.0, d=3.5, a=4.0)))
assert c is not None and c.result == "HOME", c
assert c.n_engines == 4 and c.agreeing == 3 and c.split, c
print("3. 3-of-4 (bookmaker joins DC+Elo vs xG) -> consensus HOME: OK")

# --- 4. 4-of-4 unanimous -----------------------------------------------------
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.50, 0.25, 0.25),
                      mkt.implied_1x2(_odds(h=2.0, d=3.5, a=4.0)))
assert c is not None and c.result == "HOME" and c.agreeing == 4 and not c.split, c
print("4. 4-of-4 unanimous consensus: OK")

# --- 5. market dissents -> the strongest warning -----------------------------
# DC home, Elo home, xG home, but the market favours AWAY -> 3-1, still HOME,
# with the market as the lone dissenter (the sharpest signal objecting).
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.48, 0.27, 0.25),
                      mkt.implied_1x2(_odds(h=3.8, d=3.4, a=2.0)))
assert c is not None and c.result == "HOME" and c.split, c
assert c.votes.get("AWAY") == 1, c.votes
print("5. market dissents against 3 models -> consensus flags the split: OK")

# --- 6. 2-2 tie -> NO CONSENSUS (majority needs >half of 4) ------------------
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25),
                      (0.20, 0.30, 0.50),
                      mkt.implied_1x2(_odds(h=3.8, d=3.4, a=2.0)))
assert c is not None and c.result is None and c.split, c
print("6. 2-2 tie -> NO CONSENSUS, honest: OK")

# --- 7. no odds -> no bookmaker opinion (never fabricated) --------------------
c = compute_consensus(_probs(0.50, 0.25, 0.25), (0.45, 0.30, 0.25), None, None)
assert c is not None and c.n_engines == 2, c
print("7. no odds pulled -> 2-engine consensus, bookmaker absent: OK")

# --- 8. full board renders the bookmaker line + consensus --------------------
v = VerificationResult(tier=Tier.VERIFIED, value=None)
mp = mkt.implied_1x2(_odds())
bf = BoardFixture(fixture="Home FC v Away FC (Eredivisie)", probs=_probs(),
                  verification=v, softness_tier="A",
                  elo_probs=(0.45, 0.30, 0.25), market_probs=mp,
                  consensus=compute_consensus(_probs(), (0.45, 0.30, 0.25),
                                              None, mp))
block = render_fixture_block(bf)
assert "Fourth opinion — bookmaker" in block, block
assert "margin removed" in block, block
# the consensus line reports the engine count that actually voted — here
# DC + Elo + bookmaker (xG absent) => "3 of 3 engines".
assert "CONSENSUS" in block and "engines" in block, block
assert "averaged 1X2" in block, block
# bookmaker opinion line states percentages, not raw odds
assert "to win" in block
print("8. full board renders Fourth opinion + N-of-4 consensus: OK")

# --- 9. persistence: bookmaker rows land in the brain ------------------------
from brain.store import Brain
from run_daily import _predictions_from_board
brain = Brain(_tmp / "t.db")
n = _predictions_from_board([bf], "test-run", "2026-08-06T12:00:00Z", brain)
rows = brain.predictions_for(fixture="Home FC v Away FC", engine="bookmaker")
assert len(rows) == 3, rows
by_market = {r["market"]: r["model_prob"] for r in rows}
assert abs(by_market["1X2_HOME"] - mp[0]) < 1e-9, by_market
# consensus rows also present (3-engine consensus upgraded with the market)
cons = brain.predictions_for(fixture="Home FC v Away FC", engine="consensus")
assert len(cons) == 3, cons
print("9. bookmaker + consensus rows persisted to the brain: OK")

print("\n✅ BOOKMAKER ENGINE WORKS — equal 4th vote, devigged implied 1X2,"
      " brain persistence.")
