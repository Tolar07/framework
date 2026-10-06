"""
STAKING TIED TO PROVEN EDGE (improvement #7, Architect 2026-10-02).

Suggested stake per pick/slip as a % of the Architect's bankroll. The system
never stakes; this is guidance that protects capital.

Each tier's expected ROI = a prior from the backtests, blended with its LIVE
graded record from the picks ledger (the prior counts as PRIOR_N picks, so
live results take over as they accumulate):

  est ROI > +1%        -> quarter-Kelly on that ROI, capped at 2%, floor 0.5%
  -3% .. +1%           -> 0.5%  (break-even / unproven: small)
  < -3%                -> 0.25% (proven losing: minimal)
  LOW certainty halves the stake.

Slips: 50%+ accas 0.5%, 3-leg accas (order 40) 0.25%, mega slips 0.1% — every extra
leg adds the bookmaker's margin again.

STOP-LOSS: a tier whose last 20 graded singles lost >= STOP_UNITS units is
PAUSED (stake 0) until its last-20 record recovers above that line.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

# Backtest priors (backtest/PROFIT_STUDY.md, SELECTION_STUDY.md, ANCHOR_STUDY.md)
PRIORS = {"BANKER": 0.007, "SAFE": -0.06, "BOOK": -0.06, "MARKET": -0.05,
          # VALUE (order 36): no evidence yet, so the minimal stake until live results prove it
          "VALUE": -0.05}
PRIOR_N = 100
WINDOW_DAYS = 60
STOP_UNITS = 6.0
MAX_STAKE, MIN_STAKE, SMALL, MINIMAL = 2.0, 0.5, 0.5, 0.25
SLIP_STAKES = {"safe3": 0.5, "accas": 0.25, "megas": 0.1}


def tier_stats(ledger_dir, today: Optional[str] = None) -> dict:
    """{tier: {n, roi, last20_pl, paused}} from graded singles in the window."""
    today = today or date.today().isoformat()
    since = (date.fromisoformat(today) - timedelta(days=WINDOW_DAYS)).isoformat()
    by = {}
    for path in sorted(ledger_dir.glob("picks_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not (since <= doc["date"] < today):
            continue
        for s in doc["singles"]:
            if s.get("result") not in ("won", "lost", "void"):
                continue
            pl = ((s.get("price") or 1) - 1) if s["result"] == "won" else (-1.0 if s["result"] == "lost" else 0.0)
            by.setdefault(s.get("tier") or "?", []).append((doc["date"], pl))
    out = {}
    for tier, rows in by.items():
        rows.sort()
        pls = [p for _, p in rows]
        last20 = sum(pls[-20:])
        out[tier] = {"n": len(pls), "roi": sum(pls) / len(pls),
                     "last20_pl": last20, "paused": len(pls) >= 10 and last20 <= -STOP_UNITS}
    return out


def est_roi(tier: str, stats: dict) -> float:
    prior = PRIORS.get(tier, -0.06)
    s = stats.get(tier)
    if not s:
        return prior
    return (prior * PRIOR_N + s["roi"] * s["n"]) / (PRIOR_N + s["n"])


def single_stake(tier: str, certainty: Optional[str], price: Optional[float],
                 stats: dict) -> tuple[float, str]:
    """(stake % of bankroll, reason)."""
    s = stats.get(tier) or {}
    if s.get("paused"):
        return 0.0, f"{tier} paused (stop-loss: last 20 = {s['last20_pl']:+.1f}u)"
    roi = est_roi(tier, stats)
    if roi > 0.01 and price and price > 1:
        stake = min(MAX_STAKE, max(MIN_STAKE, 100 * 0.25 * roi / (price - 1)))
        why = f"edge {roi:+.1%}"
    elif roi >= -0.03:
        stake, why = SMALL, f"break-even ({roi:+.1%})"
    else:
        stake, why = MINIMAL, f"losing tier ({roi:+.1%})"
    if certainty == "LOW":
        stake, why = stake / 2, why + ", low certainty"
    return round(stake, 2), why


def summary(stats: dict) -> str:
    parts = []
    for tier in ("BANKER", "SAFE", "VALUE", "BOOK", "MARKET"):
        s = stats.get(tier)
        roi = est_roi(tier, stats)
        state = "PAUSED" if s and s.get("paused") else f"est {roi:+.1%}"
        live = f", live {s['n']} @ {s['roi']:+.1%}" if s else ", no live record yet"
        parts.append(f"{tier} {state}{live}")
    return "Staking (% of bankroll): " + " · ".join(parts)
