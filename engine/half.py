"""
FIRST-HALF RESULT MARKETS (Architect 2026-10-05: "half-time markets").

backtest/HALF_STUDY.md: with first-half goals modelled as Poisson at the
full-match rates times the league's first-half share of goals, the model
prices the first-half RESULT well (log loss 1.0473 vs 1.0840 for base rates,
4,074 walk-forward matches; draw said 40.9%, landed 39.8%) but adds almost
nothing on first-half GOALS (Brier 0.2014 vs 0.2015), so only result markets
are used: 1st Half 1X2 (SportyBet market 60), Double Chance (63) and Draw No
Bet (64).

Chance = SportyBet's own first-half 1X2 with the margin removed + MODEL_WEIGHT
x (model - SportyBet), the same 75/25 anchor as every other pick (order 18).
These outcomes join a fixture's candidate pool — the positive-value table
(order 37) and the alternative-market legs (order 31) — but never become the
main pick, the news swap or the shaky-pick switch until they have a live
record. Graded from the first-half score: Flashscore's feed gives the
second-half score (BC/BD), so first half = full time - second half (checked on
37 of 37 matches against football-data's half-time scores, 2026-10-05).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.stats import poisson

FIRST_HALF_IDS = (60, 63, 64)
DEFAULT_SHARE = 0.445      # first-half share of goals when a league has no HT data
CACHE = Path(__file__).parent.parent / "data" / "cache"
_G = np.arange(8)
_SHARE: dict[str, float] = {}

NAMES = {"60": "1st half 1X2", "63": "1st half double chance", "64": "1st half draw no bet"}


def is_first_half(key: Optional[str]) -> bool:
    if not key or not key.startswith("SB:"):
        return False
    return key[3:].split("|", 1)[0] in NAMES


def share(league: str) -> float:
    """The league's first-half share of goals, from its cached season files."""
    if league in _SHARE:
        return _SHARE[league]
    fh = ft = 0
    for p in CACHE.glob(f"{league.replace(' ', '_')}_*.csv"):
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as fh_:
                for r in csv.DictReader(fh_):
                    try:
                        h1, a1 = int(r["HTHG"]), int(r["HTAG"])
                        h, a = int(r["FTHG"]), int(r["FTAG"])
                    except (KeyError, ValueError, TypeError):
                        continue
                    fh += h1 + a1
                    ft += h + a
        except OSError:
            continue
    _SHARE[league] = (fh / ft) if ft >= 500 else DEFAULT_SHARE
    return _SHARE[league]


def model_probs(lam_home: float, lam_away: float, league: str) -> tuple[float, float, float]:
    """(home, draw, away) for the first half."""
    s = share(league)
    m = np.outer(poisson.pmf(_G, lam_home * s), poisson.pmf(_G, lam_away * s))
    m /= m.sum()
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


def _quotes(raw_markets) -> dict:
    """{(market_id, outcome_desc): price} for the first-half result markets."""
    out = {}
    for m in raw_markets or []:
        try:
            mid = int(m.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if mid not in FIRST_HALF_IDS or (m.get("specifier") or ""):
            continue
        for o in m.get("outcomes", []):
            try:
                price = float(o.get("odds"))
            except (TypeError, ValueError):
                continue
            if price > 1 and o.get("desc"):
                out[(mid, o["desc"])] = price
    return out


def candidates(raw_markets, probs, league: str, model_weight: float,
               band=(1.20, 2.00), floor: float = 0.50) -> list[tuple]:
    """Candidate-pool tuples (chance, ev, key, model_p, market_p, MarketQuote)
    for every first-half result outcome in the odds band with chance >= floor.
    Empty when SportyBet doesn't quote the first-half 1X2 (no market anchor)."""
    from pipeline.odds import MarketQuote
    q = _quotes(raw_markets)
    x = [q.get((60, k)) for k in ("Home", "Draw", "Away")]
    if probs is None or not all(x):
        return []
    inv = [1 / p for p in x]
    kh, kd, ka = (i / sum(inv) for i in inv)
    mh, md, ma = model_probs(probs.lambda_home, probs.lambda_away, league)
    rows = {  # key -> (win model, win market, push model, push market)
        (60, "Home"): (mh, kh, 0, 0), (60, "Draw"): (md, kd, 0, 0), (60, "Away"): (ma, ka, 0, 0),
        (63, "Home or Draw"): (mh + md, kh + kd, 0, 0),
        (63, "Draw or Away"): (md + ma, kd + ka, 0, 0),
        (63, "Home or Away"): (mh + ma, kh + ka, 0, 0),
        (64, "Home"): (mh, kh, md, kd), (64, "Away"): (ma, ka, md, kd),
    }
    out = []
    for (mid, desc), (wm, wk, pm, pk) in rows.items():
        price = q.get((mid, desc))
        if not price or not (band[0] <= price <= band[1]):
            continue
        win = wk + model_weight * (wm - wk)
        push = pk + model_weight * (pm - pk)
        if win < floor:
            continue
        ev = win * price + push - 1
        out.append((round(win, 4), ev, f"SB:{mid}||{desc}", wm, wk,
                    MarketQuote(price=price, bookmaker="sportybet", n_books=1)))
    return out


def settle(key: str, fh_home: Optional[int], fh_away: Optional[int]) -> Optional[str]:
    """'won' / 'lost' / 'void' from the first-half score; None without it."""
    if fh_home is None or fh_away is None or not is_first_half(key):
        return None
    mid, _spec, out = key[3:].split("|", 2)
    h, a = fh_home, fh_away
    side = {"Home": h > a, "Draw": h == a, "Away": a > h}
    if mid == "60":
        return "won" if side.get(out) else "lost"
    if mid == "63":
        parts = [p.strip() for p in out.split(" or ")]
        return "won" if any(side.get(p) for p in parts) else "lost"
    if mid == "64":
        if h == a:
            return "void"
        return "won" if side.get(out) else "lost"
    return None
