"""Phase 3.2 — cross-league Elo blend weight tests.

The classic Elo update moves ratings by the same K-FACTOR for every match, so
in a pooled European fit a club's 38 domestic results speak exactly as loudly
as its 8 European ones — which is how a weak-league dominant ends up rated
above a strong-league club (the pool's own calibration caveat). The blend
weights each continental match by a constant `w` relative to 1.0 for domestic
ones, and fit_blend_weight() picks the w that minimises OUT-OF-SAMPLE Brier on
the pooled continental record, leaving the weight at 1.0 unless that is
provably beaten.

Proves on deterministic synthetic data:
  1. weight=1.0 reproduces the classic engine exactly (bit-identical ratings)
  2. the weight scales an update proportionally and keeps Elo zero-sum
  3. the scorer hook fires BEFORE the match touches the ratings (leak-free)
  4. evidence gate: no continental record -> NO DATA, engine untouched
  5. no-gain gate: identity is the only candidate -> left at 1.0, never forced
  6. weak-league inflation IS corrected: a farmed domestic rating is pulled
     back down by its European defeats, and the optimiser finds w > 1
  7. the applied weight beats w=1.0 on out-of-sample Brier, and the report
     says so honestly
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import MatchResult
from engine import cross_league as xl
from engine import elo as elo_engine

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_blend_"))

WEAK = "Farmland"
STRONG = "Eliteland"
UCL = "Champions League"  # in apif.BRIDGE_COMPETITIONS


_DAY = 0  # a strictly-increasing date counter so ordering is unambiguous

def _domestic(team: str, league: str, minnows: list[str], gd: int) -> list[MatchResult]:
    """Team beats each minnow home and away, always by `gd` goals. Returns 2*n
    matches on strictly-increasing dates (so rate_through's order is exact)."""
    global _DAY
    out: list[MatchResult] = []
    for mn in minnows:
        for _leg in (0, 1):  # home leg then away leg
            _DAY += 1
            d = f"2024-{(_DAY - 1) // 28 + 8:02d}-{(_DAY - 1) % 28 + 1:02d}"
            if _leg == 0:
                out.append(MatchResult(league=league, date=d, home_team=team,
                                       away_team=mn, fthg=gd, ftag=0, ftr="H"))
            else:
                out.append(MatchResult(league=league, date=d, home_team=mn,
                                       away_team=team, fthg=0, ftag=gd, ftr="A"))
    return out


def _continental(farm: str, elite: str, n: int, gd: int = 3) -> list[MatchResult]:
    """Farm loses to Elite `n` times, alternating venue, all 0-`gd` (Elite
    wins). League is a BRIDGE competition so the blend weights it."""
    out: list[MatchResult] = []
    for i in range(n):
        d = f"2025-01-{6 + i % 20:02d}"
        if i % 2 == 0:  # Farm at home, Elite wins away
            out.append(MatchResult(league=UCL, date=d, home_team=farm,
                                   away_team=elite, fthg=0, ftag=gd, ftr="A"))
        else:           # Elite at home, wins
            out.append(MatchResult(league=UCL, date=d, home_team=elite,
                                   away_team=farm, fthg=gd, ftag=0, ftr="H"))
    return out


# --- 1. weight=1.0 reproduces the classic engine exactly ---------------------
_base = _domestic("Farm", WEAK, [f"M{i}" for i in range(10)], gd=5) + \
        _domestic("Elite", STRONG, [f"E{i}" for i in range(10)], gd=1) + \
        _continental("Farm", "Elite", 8)
_pool = sorted(_base, key=lambda r: r.date)

classic = elo_engine.rate_through(_pool, burn_in=3)
weighted = elo_engine.rate_through(_pool, burn_in=3,
                                   match_weight=xl.continental_weight(1.0))
assert classic.ratings == weighted.ratings, (
    "w=1.0 must be bit-identical to the classic engine, "
    f"got {classic.ratings} vs {weighted.ratings}")
assert classic.n_matches == weighted.n_matches
print("1. continental_weight(1.0) bit-identical to classic Elo: OK")

# --- 2. the weight scales updates proportionally, zero-sum preserved ----------
_m1 = elo_engine.EloModel()
_m2 = elo_engine.EloModel()
_m1.update("A", "B", 2, 0, weight=1.0)
_m2.update("A", "B", 2, 0, weight=2.0)
d1 = _m1.rating("A") - elo_engine.BASE_RATING
d2 = _m2.rating("A") - elo_engine.BASE_RATING
assert d2 == 2.0 * d1, f"weight 2.0 must double the delta, got {d1} -> {d2}"
assert (_m1.rating("A") - elo_engine.BASE_RATING) + \
       (_m1.rating("B") - elo_engine.BASE_RATING) == 0.0, "w=1 must stay zero-sum"
assert (_m2.rating("A") - elo_engine.BASE_RATING) + \
       (_m2.rating("B") - elo_engine.BASE_RATING) == 0.0, "w=2 must stay zero-sum"
print("2. weight scales delta 2x and keeps Elo zero-sum: OK")

# --- 3. scorer hook fires BEFORE the match updates ratings (leak-free) --------
_seen: list[int] = []
def _leak_check(model: elo_engine.EloModel, r: MatchResult) -> None:
    _seen.append(model.n_matches)   # n_matches BEFORE this match is applied

rate = elo_engine.rate_through(_pool, burn_in=3, scorer=_leak_check)
assert _seen == list(range(len(_pool))), (
    "scorer must see n_matches equal to the running index (pre-update)")
assert len(_seen) == len(_pool), "scorer must fire once per match"
print("3. scorer hook fires before each update (leak-free): OK")

# --- 4. evidence gate: no continental record -> NO DATA, untouched ------------
_only_domestic = sorted(_base[:-8], key=lambda r: r.date)  # drop the UCL legs
w, info = xl.fit_blend_weight(_only_domestic, min_matches=8)
assert w == 1.0 and not info["applied"], \
    "no continental record must leave the engine untouched"
assert "NO DATA" in info["flag"], info["flag"]
print("4. evidence gate fires with no continental record: OK")

# --- 5. no-gain gate: identity is the only candidate -> never forced ----------
w5, info5 = xl.fit_blend_weight(_pool, grid=(1.0,), min_matches=8)
assert w5 == 1.0 and not info5["applied"], \
    "identity-only grid must not fabricate a change"
assert "no evidence" in info5["flag"], info5["flag"]
print("5. identity-only grid -> left at 1.0, reported honestly: OK")

# --- 6+7. weak-league inflation IS corrected; w > 1 beats w = 1 ----------------
# Farm farms a weak league 5-0 every week (gd_mod 2.0); Elite grinds its
# strong league 1-0 (gd_mod 1.0). Pure domestic Elo rates Farm above Elite —
# but in Europe Elite beats Farm 3-0 every time. The blend should read the
# direct cross-league evidence harder and pull Farm back down.
w_best, best = xl.fit_blend_weight(_pool, min_matches=8)
assert w_best > 1.0, (
    f"a farmed weak-league rating corrected by real European defeats must "
    f"find w>1, got w={w_best} info={best}")
assert best["applied"] and best["brier_best"] < best["brier_w1"], (
    f"the applied weight must beat w=1 out-of-sample, info={best}")
assert best["improvement_pp"] > 0, best
assert w_best in xl.BLEND_WEIGHT_GRID, f"{w_best} must come off the grid"
# The flag tells the Architect exactly what changed.
assert f"w={w_best}" in best["flag"] and f"+{best['improvement_pp']}pp" in best["flag"]
# And the fitted model for the winning weight rates Elite ABOVE Farm, unlike
# the classic engine — the correction is real, not cosmetic.
m_best = elo_engine.rate_through(_pool, burn_in=3,
                                 match_weight=xl.continental_weight(w_best))
m_classic = elo_engine.rate_through(_pool, burn_in=3)
assert m_best.rating("Elite") > m_best.rating("Farm"), (
    f"weighted model must rate Elite above Farm, got "
    f"Elite={m_best.rating('Elite'):.0f} Farm={m_best.rating('Farm'):.0f}")
print(f"6. optimiser corrects weak-league inflation: w={w_best}, "
      f"Brier {best['brier_w1']:.4f} -> {best['brier_best']:.4f} "
      f"(+{best['improvement_pp']}pp on {best['n_scored']} matches): OK")

print("\n✅ ALL CROSS-LEAGUE BLEND TESTS PASSED")
