"""
SHARP VALUE — pick only where SportyBet pays MORE than the sharp market's fair
price (Architect 2026-10-14: "run the sharp value list in parallel with the
current board").

WHY THIS EXISTS
  The board's own record, 332 graded singles to 13 Oct: stated 78.0%, landed
  78.0% — calibration error 0.0 points — at an average price of 1.242, which
  needs 80.5% to break even. Return -3.4%. And over 272 legs priced against
  SportyBet's OWN closing price, mean CLV -0.04% +/- 0.15%: the board's prices
  are the closing line. A calibrated model betting at the close returns minus
  the margin, every time.
  Meanwhile the board already prints, every day, that its picks sit ~5% BELOW
  the Betfair Exchange's fair odds ("Sharp check: 0 of 13 picks priced above
  ... average -5.9% vs fair") — and sends them anyway.

WHAT THIS DOES DIFFERENTLY
  One rule: take an outcome only when SportyBet's price beats the sharp
  reference's fair price by MIN_EV. No "most likely outcome", no >= 50% floor
  — those are what push every pick to 1.20-1.30, where the margin is heaviest.
  The reference is the Betfair Exchange (pipeline/sharp.py: football-data's
  free fixtures.csv carries its 1X2 and Over/Under 2.5, margin removed).

  Coverage is therefore narrow and honest: the eight outcomes the exchange
  prices (1X2 home/draw/away, double chance 1X/X2/12, Over/Under 2.5) in the
  19 of our 32 SportyBet leagues football-data gives a division code. A
  fixture the exchange does not price produces nothing — never a guess (HR35).

  This is a PARALLEL TEST, not the board: it never changes a board pick, an
  acca or a code. Both lists are graded by the same grader on the same
  fixtures, so in a few weeks the question is settled by data.
"""
from __future__ import annotations

from data.football_data_source import LEAGUE_CODES
from pipeline import sharp

MIN_EV = 0.02          # SportyBet must pay 2%+ above the exchange's fair price
BAND = (1.20, 3.00)    # wider than the board's 1.20-2.00: the bias lives at longer prices
MAX_EV = 0.25          # above this a price is stale or mismatched, not value (as order 41)

# The outcomes the exchange prices, as SportyBet ladder keys. market 1 = 1X2,
# market 10 = double chance, market 18 total=2.5 = Over/Under 2.5.
COVERED = (
    ("1", "", "Home"), ("1", "", "Draw"), ("1", "", "Away"),
    ("10", "", "Home or Draw"), ("10", "", "Draw or Away"), ("10", "", "Home or Away"),
    ("18", "total=2.5", "Over 2.5"), ("18", "total=2.5", "Under 2.5"),
)


def fair_row(fair: dict, league: str, home: str, away: str) -> dict | None:
    """The exchange's margin-free chances for one fixture, or None when
    football-data does not carry it (no code for the league, or no match)."""
    div = LEAGUE_CODES.get(league)
    return fair.get((div, home, away)) if div else None


def price_of(markets: list[dict], mid: str, spec: str,
             outcome: str) -> tuple[float | None, str | None]:
    """(SportyBet's price, outcome id) for one outcome of an OPEN market."""
    for m in markets:
        if str(m.get("id")) != mid or (m.get("specifier") or "") != spec:
            continue
        if m.get("status") not in (None, 0, "0"):
            continue                      # closed line: stale prices, not an offer
        for o in m.get("outcomes") or []:
            if (o.get("desc") or "").strip() == outcome and o.get("odds"):
                try:
                    return float(o["odds"]), o.get("id")
                except (TypeError, ValueError):
                    return None, None
    return None, None


def scan(markets: list[dict], fair: dict) -> list[dict]:
    """Every covered outcome of one fixture, with the exchange's fair chance and
    the value SportyBet's price gives against it."""
    rows = []
    for mid, spec, outcome in COVERED:
        key = f"SB:{mid}|{spec}|{outcome}"
        p = sharp.market_prob(key, fair)
        if p is None:
            continue
        price, oid = price_of(markets, mid, spec, outcome)
        if price is None or oid is None:
            continue
        rows.append({"market_id": mid, "specifier": spec, "outcome": outcome, "key": key,
                     "price": price, "outcome_id": oid, "sharp_p": round(p, 4),
                     "fair_price": round(1 / p, 3) if p else None,
                     "sharp_ev": round(p * price - 1, 4)})
    return rows


def pick(rows: list[dict], min_ev: float = MIN_EV, band: tuple = BAND,
         max_ev: float = MAX_EV) -> dict | None:
    """The one outcome of a fixture worth taking: most value above the sharp
    fair price, inside the band. None when nothing clears the bar — which is
    the normal answer and the whole point."""
    ok = [r for r in rows if band[0] <= r["price"] <= band[1] and min_ev <= r["sharp_ev"] <= max_ev]
    return max(ok, key=lambda r: r["sharp_ev"]) if ok else None


def suspect(rows: list[dict], max_ev: float = MAX_EV) -> list[dict]:
    """Outcomes whose value is too good to be true — a stale line or a mismatched
    fixture, reported rather than picked."""
    return [r for r in rows if r["sharp_ev"] > max_ev]
