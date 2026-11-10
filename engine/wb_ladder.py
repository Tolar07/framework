"""
WORLD BASKETBALL LADDERS + GAME SHAPE - twin of engine/nba_ladder.py and engine/nba_shape.py for NCAA and the
other world leagues (framework#397; Architect 2026-11-06: "NBA and basketball, they're the same thing ...
inherit all its attributes of NBA").

RECORD-ONLY. Nothing here changes a pick, a stake, a threshold or a code. The every-market record
(engine/wb_markets.py) already saves SportyBet's whole market page per game, so every points ladder is already
on disk; this reads those looks instead of fetching again:

  ladders(markets)   {market: [[line, over, under], ...]} from a recorded look (open lines only, as the NBA)
  fits(markets)      each ladder's own centre and spread, by the NBA fit (engine/nba_ladder.fit, reused)
  shape(...)         likely score, winning-margin bands and total bands - the NBA game shape run on the NCAA
                     curves (engine/ncaa_lines MARGIN_SD / TOTAL_SD); a LABEL, nothing selects on it

backtest/wb_ladder_study.py compares each ladder's implied spread with the measured NCAA spread. Missing
data (no ladder, fewer than 3 lines, no sharp line) reads PENDING, never a guess (HR35).
"""
from __future__ import annotations

import re

from engine import nba_ladder as nl
from engine import nba_shape as ns
from engine import ncaa_lines as ncl

# SportyBet points markets read as ladders (the NBA ids plus 68, the 1st-half total, and 66, the 1st-half
# handicap, which the NBA study also reads): full-game / regulation / team totals and the handicaps.
TOTAL_MARKETS = ("225", "227", "228", "18", "68")
HCP_MARKETS = ("223", "66")
# The spread real NCAA results show around ESPN's line (engine/ncaa_lines, refitted nightly by ncaa_recal).
MEASURED_SD = {"225": ncl.TOTAL_SD, "223": ncl.MARGIN_SD, "68": ncl.H1_SD}


def _num(spec: str, key: str) -> float | None:
    m = re.search(rf"{key}=(-?\d+(?:\.\d+)?)", spec or "")
    return float(m.group(1)) if m else None


def ladders(markets: list[dict]) -> dict[str, list[list[float]]]:
    """{market id: [[line, over/home price, under/away price], ...]} from a recorded look's compact markets
    ([{id, spec, open, outcomes: [[desc, price]]}], engine/nba_markets.compact_markets). Closed lines carry
    stale prices and are dropped. Handicap rows hold the HOME handicap."""
    out: dict[str, list[list[float]]] = {}
    for m in markets or []:
        mid = str(m.get("id"))
        if mid not in TOTAL_MARKETS + HCP_MARKETS or not m.get("open", True):
            continue
        px = {}
        for desc, price in m.get("outcomes") or []:
            px[(desc or "").split()[0] if desc else ""] = price
        if mid in TOTAL_MARKETS:
            line, a, b = _num(m.get("spec"), "total"), px.get("Over"), px.get("Under")
        else:
            line, a, b = _num(m.get("spec"), "hcp"), px.get("Home"), px.get("Away")
        if line is None or not a or not b or a <= 1 or b <= 1:
            continue
        out.setdefault(mid, []).append([line, a, b])
    for rows in out.values():
        rows.sort()
    return out


def fits(markets: list[dict]) -> dict[str, tuple[float, float, int] | None]:
    """Each ladder's (centre, spread, lines used) by the NBA fit; None when under 3 usable lines."""
    return {k: nl.fit(k, rows) for k, rows in ladders(markets).items()}


def shape(total: float | None, spread: float | None) -> dict | None:
    """The NBA game shape on the NCAA curves; None without both numbers (HR35)."""
    return ns.shape(total, spread, msd=ncl.MARGIN_SD, tsd=ncl.TOTAL_SD)


def verdict(implied: float | None, measured: float | None) -> str:
    if implied is None or not measured:
        return "PENDING"
    if abs(implied - measured) / measured < 0.05:
        return "about right"
    return f"WIDER by {implied - measured:.1f}" if implied > measured else f"NARROWER by {measured - implied:.1f}"
