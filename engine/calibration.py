"""
MODEL CALIBRATION — both teams to score (Architect 2026-10-05).

The model's BTTS chance runs low: over 3,550 walk-forward matches (14 leagues,
two seasons, backtest/BTTS_STUDY.md) a 40-50% model BTTS landed 52.6%, and on
3-4 Oct the model said 45% on average while BTTS landed 7 of 12. Its BTTS calls
also spread wider than the results do (a 70%+ call landed 67%).

Fix: Platt scaling on the logit — calibrated = sigmoid(A + B * logit(raw)),
fitted on all 3,550 matches. Out of sample (fit on 13 leagues, test on the
14th, every league in turn) it cut the Brier score from 0.2502 to 0.2462; fit
on the top leagues and tested on the English lower leagues, 0.2467 -> 0.2397.
Raw 35% -> 48%, 45% -> 53%, 55% -> 57%, 65% -> 61%, 75% -> 66%.

It corrects only the model's BTTS yes/no chance (the basic BTTS market and
SportyBet's "GG/NG" line, ladder market 29). The model's scoreline grid, its
other markets and the BTTS combos are unchanged. The bookmaker's side is never
touched. Refit with backtest/btts_study.py as seasons are added.
"""
from __future__ import annotations

import math
from typing import Optional

BTTS_A = 0.1892
BTTS_B = 0.4371


def btts_yes(raw: Optional[float]) -> Optional[float]:
    """The model's BTTS-yes chance, calibrated."""
    if raw is None:
        return None
    p = min(max(float(raw), 1e-4), 1 - 1e-4)
    z = BTTS_A + BTTS_B * math.log(p / (1 - p))
    return 1 / (1 + math.exp(-z))


def is_btts_key(key: str) -> Optional[bool]:
    """True for a BTTS-yes key, False for BTTS-no, None for any other market."""
    if key == "BTTS_YES":
        return True
    if key == "BTTS_NO":
        return False
    if key and key.startswith("SB:29|"):
        out = key.rsplit("|", 1)[-1].strip().lower()
        return {"yes": True, "no": False}.get(out)
    return None


def model_prob(key: str, raw: Optional[float]) -> Optional[float]:
    """The model's chance for `key` with the BTTS calibration applied; any
    other market comes back unchanged. `raw` is the model's own chance for
    that same outcome (for BTTS-no, the raw no-chance)."""
    side = is_btts_key(key)
    if side is None or raw is None:
        return raw
    if side:
        return btts_yes(raw)
    yes = btts_yes(1 - raw)
    return None if yes is None else 1 - yes
