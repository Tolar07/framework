"""
MODEL CALIBRATION — both teams to score and goals lines (Architect 2026-10-05).

The model's BTTS chance runs low: over 3,550 walk-forward matches (14 leagues,
two seasons, backtest/BTTS_STUDY.md) a 40-50% model BTTS landed 52.6%, and on
3-4 Oct the model said 45% on average while BTTS landed 7 of 12. Its BTTS calls
also spread wider than the results do (a 70%+ call landed 67%).

Fix: Platt scaling on the logit — calibrated = sigmoid(A + B * logit(raw)),
fitted on all 3,550 matches. Out of sample (fit on 13 leagues, test on the
14th, every league in turn) it cut the Brier score from 0.2502 to 0.2462; fit
on the top leagues and tested on the English lower leagues, 0.2467 -> 0.2397.
Raw 35% -> 48%, 45% -> 53%, 55% -> 57%, 65% -> 61%, 75% -> 66%.

It corrects the model's BTTS yes/no chance (basic market and SportyBet's
ladder market 29) and its match-total Over/Under 1.5 and 2.5 (basic markets
and ladder market 18). The scoreline grid, other lines, team totals and the
combos are unchanged. The bookmaker's side is never
touched. Refit with backtest/btts_study.py as seasons are added.
"""
from __future__ import annotations

import math
from typing import Optional

BTTS_A = 0.1892
BTTS_B = 0.4371

# Goals lines (same study, same method; 2026-10-05). The model under-rates
# goals: it said Over 2.5 50.6% on average and 53.5% landed, Over 1.5 74.6% vs
# 77.5%. Leave-one-league-out Brier: Over 2.5 0.2517 -> 0.2463 (better in 11 of
# 13 leagues), Over 1.5 0.1755 -> 0.1725 (10 of 13). Only the two lines that
# were tested are corrected; Over/Under 3.5 and team totals are unchanged.
OVER = {1.5: (0.6793, 0.5080), 2.5: (0.1286, 0.4170)}


def _platt(raw: float, a: float, b: float) -> float:
    p = min(max(float(raw), 1e-4), 1 - 1e-4)
    return 1 / (1 + math.exp(-(a + b * math.log(p / (1 - p)))))


def btts_yes(raw: Optional[float]) -> Optional[float]:
    """The model's BTTS-yes chance, calibrated."""
    return None if raw is None else _platt(raw, BTTS_A, BTTS_B)


def over(line: float, raw: Optional[float]) -> Optional[float]:
    """The model's Over-<line> chance, calibrated where the line was tested."""
    if raw is None or line not in OVER:
        return raw
    return _platt(raw, *OVER[line])


def goals_key(key: str) -> Optional[tuple[float, bool]]:
    """(line, is_over) for a MATCH-total Over/Under 1.5 or 2.5 key, else None."""
    fixed = {"OVER_1_5": (1.5, True), "UNDER_1_5": (1.5, False),
             "OVER_2_5": (2.5, True), "UNDER_2_5": (2.5, False)}
    if key in fixed:
        return fixed[key]
    if key and key.startswith("SB:18|"):
        try:
            spec, out = key[6:].rsplit("|", 1)
            line = float(dict(x.split("=", 1) for x in spec.split("|") if "=" in x)["total"])
        except (KeyError, ValueError):
            return None
        side = out.strip().lower()
        if line in OVER and side.startswith(("over", "under")):
            return line, side.startswith("over")
    return None


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
    if raw is None:
        return None
    g = goals_key(key)
    if g is not None:
        line, is_over = g
        o = over(line, raw if is_over else 1 - raw)
        return None if o is None else (o if is_over else 1 - o)
    side = is_btts_key(key)
    if side is None:
        return raw
    if side:
        return btts_yes(raw)
    yes = btts_yes(1 - raw)
    return None if yes is None else 1 - yes
