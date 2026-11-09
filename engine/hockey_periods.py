"""ICE HOCKEY PERIOD SPLIT (framework#381): full-game exchange price -> fair per-period 3-way prices,
and a shadow grade of a book's period price against it. RECORD ONLY: nothing here picks, stakes or
changes a rule.

Idea (Betting Talk @ 01:04-02:37, https://www.youtube.com/watch?v=tekaizJuE_M; re-implemented, no code copied):
in the NHL the favourite is the SMALLEST favourite in period 1 and larger in periods 2-3, the reverse
of the US 'biggest favourite early' rule. Books that copy that rule overprice the 1st-period favourite.

Method: regulation 1X2 (home, draw, away; the draw is the 60-minute draw) is de-vigged to fair chances.
Two Poisson goal rates (home, away) are solved so the 60-minute 1X2 matches them. A period then gets
its share of those rates. PERIOD_SHARE is an ASSUMPTION (period 1 scores least) until real period
scores are recorded; it is reported with every result and the grade reads PENDING until a sample exists.
"""
from __future__ import annotations

import math

PERIOD_SHARE = (0.31, 0.345, 0.345)     # assumption: share of goals by period; sums to 1
MAX_GOALS = 14
MIN_SAMPLE = 100                        # graded period prices before a verdict (HR35)
COMMISSION = 0.02


def _pois(lam: float) -> list[float]:
    p = [math.exp(-lam)]
    for k in range(1, MAX_GOALS + 1):
        p.append(p[-1] * lam / k)
    return p


def three_way(lh: float, la: float) -> tuple[float, float, float]:
    ph, pa = _pois(lh), _pois(la)
    h = d = a = 0.0
    for i, x in enumerate(ph):
        for j, y in enumerate(pa):
            if i > j:
                h += x * y
            elif i == j:
                d += x * y
            else:
                a += x * y
    s = h + d + a
    return h / s, d / s, a / s


def devig(h: float, d: float, a: float) -> tuple[float, float, float]:
    """Decimal prices -> fair chances (proportional margin removal)."""
    inv = [1 / h, 1 / d, 1 / a]
    s = sum(inv)
    return inv[0] / s, inv[1] / s, inv[2] / s


def _split_rates(gap: float, total: float) -> tuple[float, float]:
    lo, hi = 0.02, 0.98
    for _ in range(50):
        mid = (lo + hi) / 2
        h, _, a = three_way(total * mid, total * (1 - mid))
        lo, hi = (mid, hi) if h - a < gap else (lo, mid)
    s = (lo + hi) / 2
    return total * s, total * (1 - s)


def solve_rates(p_home: float, p_away: float, p_draw: float) -> tuple[float, float]:
    """Goal rates (home, away) whose 60-minute home/draw/away chances match the exchange: the total
    is bisected on the draw (falls as goals rise), the split on the home-minus-away gap."""
    gap = p_home - p_away
    lo, hi = 2.0, 12.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lh, la = _split_rates(gap, mid)
        _, d, _ = three_way(lh, la)
        lo, hi = (mid, hi) if d > p_draw else (lo, mid)
    return _split_rates(gap, (lo + hi) / 2)


def split(price_home: float, price_draw: float, price_away: float,
          shares: tuple[float, ...] = PERIOD_SHARE) -> dict:
    """Fair per-period chances and decimal prices from the full-game (regulation 1X2) exchange price."""
    ph, pd, pa = devig(price_home, price_draw, price_away)
    lh, la = solve_rates(ph, pa, pd)
    periods = []
    for n, sh in enumerate(shares, 1):
        h, d, a = three_way(lh * sh, la * sh)
        periods.append({"period": n, "home": h, "draw": d, "away": a,
                        "fair_home": 1 / h, "fair_draw": 1 / d, "fair_away": 1 / a})
    fav = "home" if ph >= pa else "away"
    return {"full_game": {"home": ph, "draw": pd, "away": pa}, "rates": (lh, la),
            "assumed_share": tuple(shares), "periods": periods, "favourite": fav,
            "smallest_favourite_period": min(range(len(periods)), key=lambda i: periods[i][fav]) + 1}


def grade(split_row: dict, book: dict | None, won: dict | None = None) -> dict:
    """Shadow column: a book's period prices vs fair. book = {period: {'home','draw','away'} decimal}.
    Value = book price x fair chance - 1 (2% commission is for exchange prices only, so not applied
    to a book). Missing prices read PENDING (HR35); no invented price (HR59)."""
    if not book:
        return {"status": "PENDING", "reason": "no SportyBet period prices recorded"}
    rows = []
    for p in split_row["periods"]:
        q = book.get(p["period"])
        if not q:
            rows.append({"period": p["period"], "status": "PENDING"})
            continue
        r = {"period": p["period"], "status": "OK"}
        for side in ("home", "draw", "away"):
            r[side + "_value"] = q[side] * p[side] - 1 if q.get(side) else "PENDING"
        rows.append(r)
    out = {"status": "OK", "periods": rows}
    if won is not None:
        out["n_graded"] = len(won)
        out["verdict"] = "PENDING" if len(won) < MIN_SAMPLE else "READY"
    return out
