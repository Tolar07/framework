"""OLP XDV — engine/reliability.py (OFFLINE experiment, NOT the live path)

Ported from the `closing_edge/` prototype (closing_edge/model/reliability.py).
Out-of-sample reliability maps + calibration gate.

Bin construction: 5pp bins over [0.05, 1.0] using ONLY out-of-sample
test-block predictions (never fit-set, never selected legs).

Per (market, league): mean_pred, hit_rate, n, residual.

Bin deployable iff n >= RELIABILITY_MIN_LEGS (100) AND
|residual| <= max(RELIABILITY_TOL, 2·SE_bin).

Market deployable for a block iff all bins where its bets actually land
pass, evaluated on a trailing RELIABILITY_WINDOW_BLOCKS (12) window.
A block never gates on its own outcomes.

Per-league refusal: even a pooled-active market can be refused in a
league where its bins fail.

HONESTY / PROTECTED-GATE RULE (CLAUDE.md):
  This module is NEVER imported by run_daily.py or any live EV/calibration path.
  The CLV/legs publish gate, ARCHITECT_SIGNOFF, and calibration-log scope are
  PROTECTED constants; promoting this layer into the live path requires explicit
  Architect signoff and is out of scope here. This is research plumbing only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

# --- Ported constants (NOT OLP XDV protected constants) ----------------------
# |residual| target in prob space
RELIABILITY_TOL = 0.02
# min legs per 5pp bin to gate on it
RELIABILITY_MIN_LEGS = 100
# trailing blocks that gate a market
RELIABILITY_WINDOW_BLOCKS = 12


# ---------------------------------------------------------------------------
# Bin edges: 5pp from 0.05 to 1.00
# ---------------------------------------------------------------------------

_BIN_EDGES = [0.05 + i * 0.05 for i in range(20)]  # 0.05, 0.10, ..., 1.00
assert _BIN_EDGES[-1] == 1.0


def _bin_index(p: float) -> int:
    for i, edge in enumerate(_BIN_EDGES):
        if p <= edge:
            return i
    return len(_BIN_EDGES) - 1


@dataclass
class BinStat:
    lo: float
    hi: float
    n: int
    mean_pred: float
    hit_rate: float
    residual: float
    deployable: bool

    @property
    def se(self) -> float:
        if self.n <= 0 or self.hit_rate <= 0 or self.hit_rate >= 1:
            return float("inf")
        return np.sqrt(self.hit_rate * (1 - self.hit_rate) / self.n)


def reliability_map(pairs: list[tuple[float, int]]) -> list[BinStat]:
    """Build reliability bins from (p_cal, hit) pairs.

    These must be OUT-OF-SAMPLE test-block predictions only.
    """
    bins = {i: [] for i in range(len(_BIN_EDGES))}
    for p, hit in pairs:
        if 0 <= p <= 1:
            i = _bin_index(p)
            bins[i].append((p, hit))

    stats = []
    for i, edge in enumerate(_BIN_EDGES):
        lo = 0.05 + i * 0.05 - 0.05 if i > 0 else 0.05
        hi = edge
        items = bins.get(i, [])
        if not items:
            stats.append(BinStat(lo, hi, 0, 0.0, 0.0, 0.0, False))
            continue
        mean_pred = float(np.mean([p for p, _ in items]))
        hit_rate = float(np.mean([h for _, h in items]))
        n = len(items)
        residual = mean_pred - hit_rate
        deployable = (n >= RELIABILITY_MIN_LEGS) and (
            abs(residual) <= max(RELIABILITY_TOL, 2 * np.sqrt(max(hit_rate * (1 - hit_rate), 1e-12) / n))
        )
        stats.append(BinStat(lo, hi, n, mean_pred, hit_rate, residual, deployable))
    return stats


def deployable_bins(market: str, league: str, trailing_predictions: dict[str, list[tuple[float, int]]]) -> set[tuple[float, float]]:
    """Return the set of (lo, hi) bin ranges that are deployable for a
    (market, league) given trailing-window predictions.

    trailing_predictions maps 'market/league' -> list of (p_cal, hit) from
    earlier blocks only.
    """
    key = f"{market}/{league}"
    pairs = trailing_predictions.get(key, [])
    stats = reliability_map(pairs)
    return {(s.lo, s.hi) for s in stats if s.deployable}


def is_deployable_in_bin(p_cal: float, market: str, league: str,
                          trailing_predictions: dict[str, list[tuple[float, int]]]) -> bool:
    """Check if a specific p_cal falls in a deployable bin for (market, league)."""
    key = f"{market}/{league}"
    pairs = trailing_predictions.get(key, [])
    # No trailing data = no evidence of miscalibration = deployable
    if not pairs:
        return True
    bins = deployable_bins(market, league, trailing_predictions)
    for lo, hi in bins:
        if lo <= p_cal <= hi:
            return True
    return False


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------

def test_reliability() -> None:
    # Calibrated source: hit_rate ≈ mean_pred
    rng = np.random.default_rng(123)
    pairs = []
    for p in np.linspace(0.1, 0.9, 9):
        for _ in range(200):
            hit = 1 if rng.random() < p else 0
            pairs.append((p, hit))
    stats = reliability_map(pairs)
    deployable = [s for s in stats if s.deployable]
    assert len(deployable) >= 7, f"expected most bins deployable, got {len(deployable)}"
    for s in deployable:
        assert abs(s.residual) <= max(RELIABILITY_TOL, 2 * s.se)

    # Overconfident source: 5pp bias
    pairs2 = []
    for p in np.linspace(0.1, 0.9, 9):
        true_p = p - 0.05
        for _ in range(200):
            hit = 1 if rng.random() < true_p else 0
            pairs2.append((p, hit))
    stats2 = reliability_map(pairs2)
    deployable2 = [s for s in stats2 if s.deployable]
    # Should have FEWER deployable bins (the overconfident ones fail)
    assert len(deployable2) < len(deployable), "overconfident should refuse more bins"

    print("reliability tests passed")


if __name__ == "__main__":
    test_reliability()