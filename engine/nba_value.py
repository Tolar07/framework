"""
NBA BOARD — value by PRICE COMPARISON (standing order 41, Architect
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
  1st half total (68)     ~ Normal(0.502 x sharp total, 11.9)  (NBA_STUDY Q7)
  1st quarter total (236, quarternr=1) ~ Normal(0.253 x sharp total, 8.1)
The full-game markets include overtime, as do ESPN's lines and results; the
half and quarter totals never do.

Added 2026-10-07 (Architect: "build A and B together and C";
backtest/NBA_PERIOD_STUDY.md, learned on 2023-24, held on 2024-26):
  home / away points (227 / 228) ~ Normal((T -/+ S) / 2 + b, 11.3)   incl. OT
  regulation total (18)          ~ Normal(T - 1.0, 17.2)             no OT
  1st-half handicap (66)         home margin ~ Normal(0.639 x -S, 11.0)
  quarter handicap (303, q1-q3)  home margin ~ Normal(k x -S, 8.3-8.5)
Team-by-team quarter shares were tested and did not beat one league share.
The 4th quarter and 2nd half are left out (SportyBet's overtime rule for
them is not confirmed). Whole-number lines can push and are never priced.
The Architect's own NBA method (2026-10-06) — Over a LOW points line, Under a
HIGH one, full game / 1st half / 1st quarter — is exactly what these lines
price: the board backs such a line only when SportyBet pays above its fair
price for that distance from the expected score.

A pick needs: price 1.20-2.00, chance >= 50%, value (chance x price - 1)
>= +3% on the winner market or >= +5% on a handicap / total line (the normal
curve is an approximation, so it must clear a bigger margin). Above +25% the
gap is treated as a data error (a stale line), listed for checking, never
picked. One pick per game: the best value. A LIVE TEST since 2026-10-07: the
Architect places picks by hand from their SportyBet codes (orders 26, 41).
"""
from __future__ import annotations

import re
from math import erf, sqrt
from typing import Optional

TOTAL_SD = 18.0
MARGIN_SD = 13.7
H1_SHARE, H1_SD = 0.502, 11.9     # 1st half: share of the game total, spread
Q1_SHARE, Q1_SD = 0.253, 8.1      # 1st quarter
PERIOD_MARKETS = ("68", "236")
# backtest/NBA_PERIOD_STUDY.md (the larger of the learn / test spread)
TEAM_SD, HOME_B, AWAY_B = 11.3, 0.18, 0.01
REG_B, REG_SD = -1.00, 17.2
H1_MARGIN = (0.639, 11.0)
Q_MARGIN = {1: (0.331, 8.3), 2: (0.308, 8.2), 3: (0.320, 8.5)}
TEAM_MARKETS = ("227", "228")
HCP_PERIOD_MARKETS = ("66", "303")
MARKETS = ("219", "223", "225") + PERIOD_MARKETS + TEAM_MARKETS + ("18",) + HCP_PERIOD_MARKETS
# The spread real results show per market — for the ladder study (engine/nba_ladder keys).
MEASURED_SD = {"225": TOTAL_SD, "227": TEAM_SD, "228": TEAM_SD, "18": REG_SD,
               "223": MARGIN_SD, "66": H1_MARGIN[1],
               **{f"303/q{n}": sd for n, (_k, sd) in Q_MARGIN.items()}}
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


def _over(line: float, mean: float, sd: float, side: str) -> float | None:
    p_over = 1 - _phi((line - mean) / sd)
    return p_over if side == "Over" else (1 - p_over if side == "Under" else None)


def _home_covers(h: float, mean: float, sd: float, side: str) -> float | None:
    """Chance a HOME handicap h is covered (home margin > -h), or the away side."""
    p_home = 1 - _phi((-h - mean) / sd)
    return p_home if side == "Home" else (1 - p_home if side == "Away" else None)


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
    if market_id in ("225",) + PERIOD_MARKETS:
        m = re.search(r"total=(\d+(?:\.\d+)?)", specifier or "")
        if sharp.total is None or not m:
            return None
        if market_id == "236" and "quarternr=1" not in (specifier or ""):
            return None                          # 1st quarter only
        mean, sd = {"225": (sharp.total, TOTAL_SD),
                    "68": (H1_SHARE * sharp.total, H1_SD),
                    "236": (Q1_SHARE * sharp.total, Q1_SD)}[market_id]
        line = float(m.group(1))
        p_over = 1 - _phi((line - mean) / sd)
        return p_over if side == "Over" else (1 - p_over if side == "Under" else None)
    if market_id in TEAM_MARKETS + ("18",):
        m = re.search(r"total=(\d+(?:\.\d+)?)", specifier or "")
        if sharp.total is None or not m or float(m.group(1)) == int(float(m.group(1))):
            return None
        line = float(m.group(1))
        if market_id == "18":
            return _over(line, sharp.total + REG_B, REG_SD, side)
        if sharp.spread is None:
            return None
        mean = ((sharp.total - sharp.spread) / 2 + HOME_B if market_id == "227"
                else (sharp.total + sharp.spread) / 2 + AWAY_B)
        return _over(line, mean, TEAM_SD, side)
    if market_id in HCP_PERIOD_MARKETS:
        m = re.search(r"hcp=(-?\d+(?:\.\d+)?)", specifier or "")
        if sharp.spread is None or not m:
            return None
        h = float(m.group(1))
        if h == int(h):
            return None
        if market_id == "66":
            k, sd = H1_MARGIN
        else:
            q = re.search(r"quarternr=(\d)", specifier or "")
            if not q or int(q.group(1)) not in Q_MARGIN:
                return None                          # quarters 1-3 only
            k, sd = Q_MARGIN[int(q.group(1))]
        return _home_covers(h, k * -sharp.spread, sd, side)
    return None


def candidates(event: dict, sharp) -> tuple[list[dict], list[dict]]:
    """(value picks, suspect gaps) for one SportyBet event against its sharp line."""
    picks, suspect = [], []
    for m in event.get("markets", []):
        mid = str(m.get("id"))
        if mid not in MARKETS:
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
    if mid == "68":
        return f"1st half {o} points"
    if mid == "236":
        return f"1st quarter {o} points"
    if mid in TEAM_MARKETS:
        return f"{home if mid == '227' else away} {o} points (incl. OT)"
    if mid == "18":
        return f"{o} points (regulation time, no OT)"
    if mid in HCP_PERIOD_MARKETS:
        m = re.search(r"\(([-+]?\d+(?:\.\d+)?)\)", o)
        team = home if o.startswith("Home") else away
        q = re.search(r"quarternr=(\d)", row.get("specifier") or "")
        period = "1st half" if mid == "66" else f"{('1st', '2nd', '3rd')[int(q.group(1)) - 1]} quarter" if q else "quarter"
        return f"{team} ({m.group(1) if m else '?'}) {period} handicap"
    return o


def settle(row: dict, hs: int, as_: int, q_home: Optional[list] = None,
           q_away: Optional[list] = None) -> Optional[str]:
    """'won' / 'lost' for a pick from the final score (incl. OT) — or, for a
    1st-half / 1st-quarter total, from the quarter scores — or None."""
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
    if mid in PERIOD_MARKETS:
        m = re.search(r"total=(\d+(?:\.\d+)?)", spec)
        n = 2 if mid == "68" else 1
        if not m or not q_home or not q_away or len(q_home) < n or len(q_away) < n:
            return None
        pts = sum(q_home[:n]) + sum(q_away[:n])
        return "won" if (o.startswith("Over") == (pts > float(m.group(1)))) else "lost"
    if mid in TEAM_MARKETS:
        m = re.search(r"total=(\d+(?:\.\d+)?)", spec)
        if not m:
            return None
        pts = hs if mid == "227" else as_
        return "won" if (o.startswith("Over") == (pts > float(m.group(1)))) else "lost"
    if mid == "18":
        m = re.search(r"total=(\d+(?:\.\d+)?)", spec)
        if not m or not q_home or not q_away or len(q_home) < 4 or len(q_away) < 4:
            return None
        pts = sum(q_home[:4]) + sum(q_away[:4])
        return "won" if (o.startswith("Over") == (pts > float(m.group(1)))) else "lost"
    if mid in HCP_PERIOD_MARKETS:
        m = re.search(r"hcp=(-?\d+(?:\.\d+)?)", spec)
        if not m or not q_home or not q_away:
            return None
        if mid == "66":
            if len(q_home) < 2 or len(q_away) < 2:
                return None
            margin = sum(q_home[:2]) - sum(q_away[:2])
        else:
            q = re.search(r"quarternr=(\d)", spec)
            n = int(q.group(1)) if q else 0
            if not 1 <= n <= 3 or len(q_home) < n or len(q_away) < n:
                return None
            margin = q_home[n - 1] - q_away[n - 1]
        home_covers = margin + float(m.group(1)) > 0
        return "won" if (o.startswith("Home") == home_covers) else "lost"
    return None
