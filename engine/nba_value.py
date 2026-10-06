"""
NBA PAPER BOARD — value by PRICE COMPARISON (standing order 41, Architect
2026-10-06: "Yes, build the paper NBA board").

backtest/NBA_STUDY.md showed the football method (pick the likeliest outcome)
loses the bookmaker's margin on the NBA: the closing line is sharper than any
rating model. So this board does one thing only: it compares each SportyBet
NBA price with a FAIR price taken from the sharp line (ESPN BET via ESPN, the
margin removed) and lists a pick only when SportyBet pays MORE than fair.

Fair chances
  winner (219)     the sharp moneyline with its margin removed
  handicap (223)   home margin ~ Normal(-sharp spread, 13.7)   (NBA_STUDY Q-margin)
  total (225)      final total ~ Normal(sharp total, 18.0)     (NBA_STUDY Q5)
All SportyBet NBA markets include overtime, as do ESPN's lines and results.

A pick needs: price 1.20-2.00, chance >= 50%, value (chance x price - 1)
>= +3% on the winner market or >= +5% on a handicap / total line (the normal
curve is an approximation, so it must clear a bigger margin). Above +25% the
gap is treated as a data error (a stale line), listed for checking, never
picked. One pick per game: the best value. PAPER ONLY — no stake, no capital
(order 26 is unchanged) until the graded record shows it works.
"""
from __future__ import annotations

import re
from math import erf, sqrt
from typing import Optional

TOTAL_SD = 18.0
MARGIN_SD = 13.7
BAND = (1.20, 2.00)
MIN_CHANCE = 0.50
MIN_EV_WINNER = 0.03
MIN_EV_LINE = 0.05
MAX_EV = 0.25
MAX_ML_GAP = 0.12        # SportyBet vs sharp winner chance: bigger = wrong match / stale


def _phi(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def devig(a: float, b: float) -> float:
    """Chance of the first side from two decimal prices, margin removed."""
    s = 1 / a + 1 / b
    return (1 / a) / s


def fair_chance(market_id: str, specifier: str, outcome: str, sharp) -> Optional[float]:
    """Fair chance of one SportyBet outcome from the sharp line, or None.

    `sharp` has ml_home, ml_away, spread (home line), total. `outcome` is
    SportyBet's desc: "Home"/"Away", "Home (-4.5)"/"Away (+4.5)", "Over 220.5"."""
    side = outcome.split()[0] if outcome else ""
    if market_id == "219":
        if not (sharp.ml_home and sharp.ml_away):
            return None
        p = devig(sharp.ml_home, sharp.ml_away)
        return p if side == "Home" else (1 - p if side == "Away" else None)
    if market_id == "223":
        m = re.search(r"hcp=(-?\d+(?:\.\d+)?)", specifier or "")
        if sharp.spread is None or not m:
            return None
        h = float(m.group(1))                    # the HOME handicap of this line
        if h == int(h):
            return None                          # a whole-number line can push
        mean = -sharp.spread                     # expected home margin
        p_home = 1 - _phi((-h - mean) / MARGIN_SD)
        return p_home if side == "Home" else (1 - p_home if side == "Away" else None)
    if market_id == "225":
        m = re.search(r"total=(\d+(?:\.\d+)?)", specifier or "")
        if sharp.total is None or not m:
            return None
        line = float(m.group(1))
        p_over = 1 - _phi((line - sharp.total) / TOTAL_SD)
        return p_over if side == "Over" else (1 - p_over if side == "Under" else None)
    return None


def candidates(event: dict, sharp) -> tuple[list[dict], list[dict]]:
    """(value picks, suspect gaps) for one SportyBet event against its sharp line."""
    picks, suspect = [], []
    for m in event.get("markets", []):
        mid = str(m.get("id"))
        if mid not in ("219", "223", "225"):
            continue
        spec = m.get("specifier") or ""
        for o in m.get("outcomes", []):
            try:
                price = float(o.get("odds"))
            except (TypeError, ValueError):
                continue
            if not (BAND[0] <= price <= BAND[1]) or o.get("id") is None:
                continue
            p = fair_chance(mid, spec, o.get("desc", ""), sharp)
            if p is None or p < MIN_CHANCE:
                continue
            ev = p * price - 1
            row = {"market_id": mid, "specifier": spec, "outcome": o.get("desc", ""),
                   "outcome_id": o.get("id"), "price": price, "chance": round(p, 4),
                   "fair_price": round(1 / p, 3), "ev": round(ev, 4)}
            if ev > MAX_EV:
                suspect.append(row)
            elif ev >= (MIN_EV_WINNER if mid == "219" else MIN_EV_LINE):
                picks.append(row)
    return picks, suspect


def sportybet_winner_chance(event: dict) -> Optional[float]:
    for m in event.get("markets", []):
        if str(m.get("id")) == "219":
            px = {o.get("desc"): o.get("odds") for o in m.get("outcomes", [])}
            try:
                return devig(float(px["Home"]), float(px["Away"]))
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                return None
    return None


def display(row: dict, home: str, away: str) -> str:
    o, mid = row["outcome"], row["market_id"]
    if mid == "219":
        return f"{home if o == 'Home' else away} to win (incl. OT)"
    if mid == "223":
        m = re.search(r"\(([-+]?\d+(?:\.\d+)?)\)", o)
        team = home if o.startswith("Home") else away
        return f"{team} ({m.group(1) if m else '?'}) handicap"
    if mid == "225":
        return f"{o} points (incl. OT)"
    return o


def settle(row: dict, hs: int, as_: int) -> Optional[str]:
    """'won' / 'lost' for a pick from the final score (incl. OT), or None."""
    o, mid, spec = row["outcome"], row["market_id"], row.get("specifier") or ""
    if mid == "219":
        return "won" if (o == "Home") == (hs > as_) else "lost"
    if mid == "223":
        m = re.search(r"hcp=(-?\d+(?:\.\d+)?)", spec)
        if not m:
            return None
        h = float(m.group(1))
        home_covers = hs + h > as_
        return "won" if (o.startswith("Home") == home_covers) else "lost"
    if mid == "225":
        m = re.search(r"total=(\d+(?:\.\d+)?)", spec)
        if not m:
            return None
        over = hs + as_ > float(m.group(1))
        return "won" if (o.startswith("Over") == over) else "lost"
    return None
