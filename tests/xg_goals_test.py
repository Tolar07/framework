"""Phase 3.4 — xG goals-market integration (O1.5/O2.5/O3.5/BTTS).

predict_xg already produced an over25/btts, but they were never surfaced and
the over25 formula was WRONG: `1 - P(home<=4)*P(away<=4)` measures "at least
one team scores 5+", a different event from "total goals >= 3". For a
1.5-vs-1.5 match it said ~3.7% when the true O2.5 is ~57.7%. Phase 3.4 fixes
the goals probabilities, surfaces xG's goals read on the board beside DC's
(never blended), and raises a GOALS DIVERGENCE flag when the goals model and
the chances model disagree materially — the same honesty structure as the
1X2 engine divergence.

Honesty rules proven here:
  1. goals markets come from the SAME xG prediction, monotone across lines
     (O1.5 >= O2.5 >= O3.5) and close to an independent reference sum
  2. the over25 regression: the old formula said ~0.72 for a 4.5-4.5 match,
     the corrected read is >=0.97 (and the reference for a balanced 1.5-1.5
     match is ~0.58, not ~0.04)
  3. btts matches the exact P(H>=1)*P(A>=1)
  4. goals_divergence: agreement -> None; a >=20pt gap -> a flag naming the
     market; a missing number on either side -> None (HR35: absence is never
     a pass or a flag)
  5. the board renders xG's goals read + the divergence flag beside DC's
  6. xG goals rows land in the brain under model_engine='xg', so engine_clv
     attributes goals-market CLV to xG (Phase 3.3) — never to DC
"""
import math
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import xg_source
from output.produce_bet import BoardFixture, render_fixture_block
from verification.id403 import SourcedDatum as _SD
from verification.id403 import verify as _verify

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_xg_goals_"))


def _pmf(k: float, lam: float) -> float:
    """Independent Poisson pmf — deliberately NOT the module's helper."""
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _ref_over(line: int, lam_h: float, lam_a: float) -> float:
    """Independent reference: exact truncated sum over a wide support."""
    return sum(_pmf(i, lam_h) * _pmf(j, lam_a)
               for i in range(30) for j in range(30) if i + j > line)


# Ratings that give clean lambdas (2.0, 1.0) with home_adv=0.0:
# lam_h = 2.0 * 1.0 + 0.0 = 2.0 ; lam_a = 1.0 * 1.0 = 1.0.
ratings = {
    "Home FC": xg_source.TeamXG("Home FC", 2.0, 1.0, 20),
    "Away FC": xg_source.TeamXG("Away FC", 1.0, 1.0, 20),
}

# --- 1. goals markets: monotone, bounded, close to the independent reference --
p = xg_source.predict_xg("Home FC", "Away FC", ratings, league="", home_adv=0.0)
assert p is not None
assert 0 < p.over15 < 1 and 0 < p.over25 < 1 and 0 < p.over35 < 1
assert 0 < p.btts < 1
assert p.over15 >= p.over25 >= p.over35, f"lines not monotone: {p}"
for attr, line in (("over15", 1), ("over25", 2), ("over35", 3)):
    ref = _ref_over(line, 2.0, 1.0)
    assert abs(getattr(p, attr) - ref) < 1e-6, \
        f"{attr}: got {getattr(p, attr)} vs reference {ref}"
print("1. goals markets monotone + match independent reference: OK")

# --- 2. the over25 regression: corrected, not the old wrong event -------------
old_wrong = 1 - sum(_pmf(i, 4.5) for i in range(5)) * sum(_pmf(j, 4.5) for j in range(5))
assert old_wrong < 0.9, f"old formula read {old_wrong} for a 4.5-4.5 match"
hi = {
    "Home FC": xg_source.TeamXG("Home FC", 4.5, 1.0, 20),
    "Away FC": xg_source.TeamXG("Away FC", 4.5, 1.0, 20),
}
p_hi = xg_source.predict_xg("Home FC", "Away FC", hi, league="", home_adv=0.0)
assert p_hi is not None and p_hi.over25 >= 0.97, \
    f"corrected O2.5 for a 4.5-4.5 match must be near certain, got {p_hi.over25}"
# a balanced ~1.5-1.5 match must read ~0.58, not the old ~0.04
ref_15 = _ref_over(2, 1.5, 1.5)
assert 0.50 < ref_15 < 0.65, f"1.5-1.5 reference O2.5 = {ref_15}"
print("2. over25 corrected (was measuring 'some team scores 5+'): OK")

# --- 3. btts = P(H>=1) * P(A>=1), exact ---------------------------------------
btts_ref = (1 - _pmf(0, 2.0)) * (1 - _pmf(0, 1.0))
assert abs(p.btts - btts_ref) < 1e-9, f"btts {p.btts} vs {btts_ref}"
print("3. btts exact formula: OK")

# --- 4. goals_divergence: gated, material-gap flag, HR35 on absence -----------
xg_agree = xg_source.XGProbabilities(home=0.4, draw=0.3, away=0.3,
                                     over15=0.8, over25=0.577, over35=0.35,
                                     btts=0.547)
# within tolerance on both markets -> None (consistent reads, no flag)
agree = SimpleNamespace(p_over_25=0.55, p_btts_yes=0.60)
assert xg_source.goals_divergence(agree, xg_agree) is None, \
    xg_source.goals_divergence(agree, xg_agree)
# a >=20pt gap on O2.5 -> a flag that NAMES the market
gap = SimpleNamespace(p_over_25=0.85, p_btts_yes=0.60)
flag = xg_source.goals_divergence(gap, xg_agree)
assert flag is not None and "O2.5" in flag and "85%" in flag, flag
# a missing number on either side -> None (HR35: never flagged or passed)
missing = SimpleNamespace(p_over_25=None, p_btts_yes=None)
assert xg_source.goals_divergence(missing, xg_agree) is None
assert xg_source.goals_divergence(None, xg_agree) is None
assert xg_source.goals_divergence(agree, None) is None
print("4. goals_divergence gated, named, HR35 on absence: OK")

# --- 5. the wide board renders xG's goals read + the divergence flag ----------
class _ProbsDisagree:
    home_team = "Home FC"
    away_team = "Away FC"
    p_home, p_draw, p_away = 0.45, 0.25, 0.30
    p_over_15, p_over_25, p_over_35 = 0.78, 0.85, 0.30
    p_btts_yes, lambda_home, lambda_away = 0.62, 1.6, 1.4


_v = _verify([_SD(domain="thesportsdb.com", value="x", url="http://x")])
xp = xg_source.predict_xg("Home FC", "Away FC", ratings, league="", home_adv=0.0)
bf = BoardFixture(
    fixture="Home FC v Away FC (Bundesliga)",
    probs=_ProbsDisagree(), verification=_v,
    xg_probs=(xp.home, xp.draw, xp.away),
    xg_goals=(xp.over15, xp.over25, xp.over35, xp.btts),
    goals_divergence=xg_source.goals_divergence(_ProbsDisagree(), xp),
)
block = render_fixture_block(bf)
assert "Goals (chance quality)" in block, f"xG goals read missing: {block}"
assert "GOALS DIVERGENCE" in block and "O2.5" in block, \
    f"divergence flag missing from board: {block}"
# a fixture WITHOUT xg_goals must not crash and must not fabricate the line
bf_noxg = BoardFixture(fixture="Nijmegen v Telstar (Eredivisie)",
                       probs=_ProbsDisagree(), verification=_v,
                       xg_probs=(xp.home, xp.draw, xp.away))
assert "Goals (chance quality)" not in render_fixture_block(bf_noxg)
print("5. board renders xG goals + divergence flag: OK")

# --- 6. xG goals rows land in the brain under model_engine='xg' ----------------
from brain.store import Brain  # noqa: E402
from run_daily import _predictions_from_board  # noqa: E402

brain = Brain(_tmp / "xg.db")
bf_full = BoardFixture(
    fixture="Home FC v Away FC (Bundesliga)",
    probs=_ProbsDisagree(), verification=_v,
    xg_probs=(xp.home, xp.draw, xp.away),
    xg_goals=(xp.over15, xp.over25, xp.over35, xp.btts),
    softness_tier="A", kickoff_date="2026-08-10", model_engine="dc",
)
n = _predictions_from_board([bf_full], "xgrun", "2026-08-09T00:00:00+00:00", brain)
res = brain.predictions_for(run_id="xgrun", engine="xg")
markets = {r["market"] for r in res}
assert {"1X2_HOME", "1X2_DRAW", "1X2_AWAY",
        "OVER_1_5", "OVER_2_5", "BTTS_YES"} <= markets, markets
assert all(r["model_engine"] == "xg" for r in res), (
    "every xG goals row must carry model_engine='xg' so CLV attribution "
    "goes to xG, never to DC")
# the goals rows are graded per-market like any other prediction
o25 = [r for r in res if r["market"] == "OVER_2_5"]
assert len(o25) == 1 and abs(o25[0]["model_prob"] - xp.over25) < 1e-9
brain.close()
print("6. xG goals rows persist under model_engine='xg': OK")

print("\n✅ ALL XG GOALS-MARKET TESTS PASSED")
