"""
FULL MARKET LADDER — price every SportyBet market settled on the final score.

Architect 2026-10-02: "look at the full betting market" — Draw No Bet, Asian
and European handicaps, team goals, clean sheets, win-to-nil, goal ranges,
Multigoals, Double Chance & Over/Under, 1X2 & Over/Under, BTTS combos ...

Every outcome becomes a rule on the final score (h, a) -> win / push / lose,
and is priced from a scoreline grid:
  * MODEL grid  — Dixon-Coles (engine.dixon_coles.score_matrix), fitted on
                  match history;
  * MARKET grid — two Poisson rates fitted to SportyBet's own de-vigged 1X2
                  and Over/Under 2.5, i.e. the bookmaker's view of the game.
A push (stake returned: DNB on a draw, Asian handicap on a whole line) is
tracked separately, so "no-loss" = win + push.

Half-time, first-goal and correct-score markets are NOT priced (no half-time
model; correct scores sit far outside the 1.20-2.00 band). Quarter-ball Asian
lines (x.25 / x.75) are skipped rather than approximated (HR35).
"""
from __future__ import annotations

import re
from typing import Callable, Optional

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

MAX_G = 10
_G = np.arange(MAX_G + 1)
H_GRID, A_GRID = np.meshgrid(_G, _G, indexing="ij")

# SportyBet market ids fetched for the ladder (full-time markets only).
LADDER_MARKET_IDS = (1, 10, 11, 12, 13, 14, 16, 18, 19, 20, 21, 23, 24, 25, 26,
                     29, 30, 31, 32, 33, 34, 36, 37, 546, 547, 548)

Rule = Callable[[int, int], str]   # -> "win" | "push" | "lose"

# A line whose price implies a probability this far BELOW what the book's own
# 1X2 + goals prices give that outcome is treated as mislabeled/stale and is
# never picked (see run_daily LINE CONSISTENCY GUARD).
LINE_TOLERANCE = 0.08


def _b(cond: bool) -> str:
    return "win" if cond else "lose"


def _spec(specifier: str) -> dict:
    out = {}
    for part in (specifier or "").split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def _side(word: str) -> Optional[Callable[[int, int], bool]]:
    word = word.strip().lower()
    return {"home": lambda h, a: h > a, "draw": lambda h, a: h == a,
            "away": lambda h, a: a > h,
            "home/draw": lambda h, a: h >= a, "home or draw": lambda h, a: h >= a,
            "draw/away": lambda h, a: a >= h, "draw or away": lambda h, a: a >= h,
            "home/away": lambda h, a: h != a, "home or away": lambda h, a: h != a,
            }.get(word)


def _ou(word: str, total: float, value_of: Callable[[int, int], int]):
    word = word.strip().lower()
    if word.startswith("over"):
        return lambda h, a: ("push" if value_of(h, a) == total else _b(value_of(h, a) > total))
    if word.startswith("under"):
        return lambda h, a: ("push" if value_of(h, a) == total else _b(value_of(h, a) < total))
    return None


def _range(text: str):
    t = text.strip()
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return lambda n: lo <= n <= hi
    m = re.fullmatch(r"(\d+)\+", t)
    if m:
        lo = int(m.group(1))
        return lambda n: n >= lo
    if t.isdigit():
        k = int(t)
        return lambda n: n == k
    return None


def rule_for(market_id, specifier: str, outcome: str) -> Optional[Rule]:
    """win/push/lose rule for one SportyBet outcome, or None if unsupported."""
    mid = int(market_id)
    sp = _spec(specifier)
    o = (outcome or "").strip()
    ol = o.lower()
    tot = lambda h, a: h + a
    if mid == 1 or mid == 10:
        f = _side(o)
        return (lambda h, a: _b(f(h, a))) if f else None
    if mid == 11:      # Draw No Bet
        if ol in ("home", "away"):
            f = _side(ol)
            return lambda h, a: "push" if h == a else _b(f(h, a))
        return None
    if mid == 12:      # Home No Bet: void if home wins
        f = _side(ol)
        return (lambda h, a: "push" if h > a else _b(f(h, a))) if ol in ("draw", "away") else None
    if mid == 13:      # Away No Bet: void if away wins
        f = _side(ol)
        return (lambda h, a: "push" if a > h else _b(f(h, a))) if ol in ("home", "draw") else None
    if mid == 14:      # European handicap hcp=x:y (3-way, no push)
        m = re.fullmatch(r"(\d+):(\d+)", sp.get("hcp", ""))
        if not m:
            return None
        hx, ax = int(m.group(1)), int(m.group(2))
        f = _side(ol.split(" (")[0])
        return (lambda h, a: _b(f(h + hx, a + ax))) if f else None
    if mid == 16:      # Asian handicap hcp = home line
        try:
            line = float(sp.get("hcp", ""))
        except ValueError:
            return None
        if abs((line * 2) - round(line * 2)) > 1e-9:
            return None    # quarter lines skipped
        who = ol.split(" (")[0]
        if who not in ("home", "away"):
            return None
        def r(h, a, line=line, who=who):
            d = (h - a + line) if who == "home" else (a - h - line)
            return "push" if d == 0 else _b(d > 0)
        return r
    if mid in (18, 19, 20):
        try:
            t = float(sp.get("total", ""))
        except ValueError:
            return None
        val = {18: tot, 19: lambda h, a: h, 20: lambda h, a: a}[mid]
        return _ou(ol, t, val)
    if mid in (21, 23, 24, 25, 548):
        f = _range(o)
        if not f:
            return None
        val = {21: tot, 25: tot, 548: tot, 23: lambda h, a: h, 24: lambda h, a: a}[mid]
        return lambda h, a: _b(f(val(h, a)))
    if mid == 26:
        return {"odd": lambda h, a: _b((h + a) % 2 == 1),
                "even": lambda h, a: _b((h + a) % 2 == 0)}.get(ol)
    if mid == 29:
        return {"yes": lambda h, a: _b(h > 0 and a > 0),
                "no": lambda h, a: _b(not (h > 0 and a > 0))}.get(ol)
    if mid == 30:
        return {"none": lambda h, a: _b(h == 0 and a == 0),
                "only home": lambda h, a: _b(h > 0 and a == 0),
                "only away": lambda h, a: _b(a > 0 and h == 0),
                "both teams": lambda h, a: _b(h > 0 and a > 0)}.get(ol)
    if mid in (31, 32, 33, 34):
        cond = {31: lambda h, a: a == 0, 32: lambda h, a: h == 0,
                33: lambda h, a: h > a and a == 0, 34: lambda h, a: a > h and h == 0}[mid]
        if ol == "yes":
            return lambda h, a: _b(cond(h, a))
        if ol == "no":
            return lambda h, a: _b(not cond(h, a))
        return None
    if mid in (36, 37, 546, 547):
        if " & " not in o:
            return None
        left, right = (x.strip() for x in o.split(" & ", 1))
        if mid == 36:     # "Over 2.5 & Yes"
            try:
                t = float(sp.get("total", ""))
            except ValueError:
                return None
            g = _ou(left, t, tot)
            btts = {"yes": True, "no": False}.get(right.lower())
            if g is None or btts is None:
                return None
            return lambda h, a: _b(g(h, a) == "win" and ((h > 0 and a > 0) == btts))
        f = _side(left)
        if f is None:
            return None
        if mid == 546:    # "Home/Draw & Yes"
            btts = {"yes": True, "no": False}.get(right.lower())
            if btts is None:
                return None
            return lambda h, a: _b(f(h, a) and ((h > 0 and a > 0) == btts))
        try:
            t = float(sp.get("total", ""))
        except ValueError:
            return None
        g = _ou(right, t, tot)
        if g is None:
            return None
        return lambda h, a: _b(f(h, a) and g(h, a) == "win")
    return None


def evaluate(matrix: np.ndarray, rule: Rule) -> tuple[float, float]:
    """(P(win), P(push)) of a rule under a scoreline grid."""
    win = push = 0.0
    n = matrix.shape[0]
    for h in range(n):
        for a in range(n):
            r = rule(h, a)
            if r == "win":
                win += matrix[h, a]
            elif r == "push":
                push += matrix[h, a]
    return float(win), float(push)


def _devig(prices):
    inv = [1 / p for p in prices]
    s = sum(inv)
    return [i / s for i in inv]


def market_matrix(fx) -> Optional[np.ndarray]:
    """The bookmaker's scoreline grid: independent Poisson rates fitted to the
    de-vigged 1X2 and Over/Under 2.5 prices. None if those aren't quoted."""
    try:
        H, D, A = fx.home.price, fx.draw.price, fx.away.price
        OV, UN = fx.over25.price, fx.under25.price
    except AttributeError:
        return None
    if not all((H, D, A, OV, UN)):
        return None
    ph, pd, pa = _devig([H, D, A])
    pov, _ = _devig([OV, UN])

    def grid(x):
        lh, la = np.exp(x)
        return np.outer(poisson.pmf(_G, lh), poisson.pmf(_G, la))

    def loss(x):
        m = grid(x)
        m = m / m.sum()
        return ((np.tril(m, -1).sum() - ph) ** 2 + (np.triu(m, 1).sum() - pa) ** 2
                + (np.trace(m) - pd) ** 2 + (m[(H_GRID + A_GRID) > 2].sum() - pov) ** 2)

    res = minimize(loss, x0=np.log([1.4, 1.1]), method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 400})
    m = grid(res.x)
    return m / m.sum()


def key(market_id, specifier: str, outcome: str) -> str:
    return f"SB:{int(market_id)}|{specifier or ''}|{outcome}"


def parse_key(k: str) -> Optional[tuple[int, str, str]]:
    if not k or not k.startswith("SB:"):
        return None
    mid, spec, outcome = k[3:].split("|", 2) if k.count("|") >= 2 else (None, None, None)
    if mid is None:
        return None
    # specifiers can themselves contain '|' (e.g. 'minsnr=10|total=1.5'); the
    # outcome never does, so split from the right for it.
    head, outcome = k[3:].rsplit("|", 1)
    mid, spec = head.split("|", 1)
    return int(mid), spec, outcome


def settle_key(k: str, fthg: int, ftag: int) -> Optional[bool]:
    """True/False for a won/lost ladder leg; None for a push or unknown rule."""
    pk = parse_key(k)
    if not pk:
        return None
    r = rule_for(*pk)
    if r is None:
        return None
    res = r(fthg, ftag)
    return None if res == "push" else res == "win"


_NAMES = {1: "1X2", 10: "Double Chance", 11: "Draw No Bet", 12: "Home No Bet",
          13: "Away No Bet", 14: "Handicap", 16: "Asian Handicap", 18: "Goals",
          21: "Exact Goals", 23: "Home Goals", 24: "Away Goals", 25: "Goal Range",
          26: "Odd/Even", 29: "BTTS", 30: "Teams to Score", 31: "Home Clean Sheet",
          32: "Away Clean Sheet", 33: "Home Win to Nil", 34: "Away Win to Nil",
          36: "Goals & BTTS", 37: "1X2 & Goals", 546: "DC & BTTS", 547: "DC & Goals",
          548: "Multigoals"}


def display_key(k: str, home: str = "Home", away: str = "Away") -> str:
    """Plain words for a ladder key, with team names in place of Home/Away."""
    pk = parse_key(k)
    if not pk:
        return k
    mid, spec, outcome = pk
    sp = _spec(spec)
    sub = lambda s: (s.replace("Home", home).replace("Away", away)
                     .replace("home", home).replace("away", away))
    if mid == 1:
        return {"Home": f"{home} to win", "Away": f"{away} to win"}.get(outcome, "Draw")
    if mid == 10:
        return {"Home or Draw": f"{home} or draw", "Draw or Away": f"{away} or draw",
                "Home or Away": f"{home} or {away}"}.get(outcome, outcome)
    if mid == 11:
        return f"{sub(outcome)} (draw no bet)"
    if mid == 16:
        return f"{sub(outcome)} Asian handicap"
    if mid == 14:
        return f"{sub(outcome)} handicap"
    if mid == 18:
        return f"{outcome} goals"
    if mid == 19:
        return f"{home} {outcome} goals"
    if mid == 20:
        return f"{away} {outcome} goals"
    if mid == 29:
        return f"Both teams to score — {outcome.lower()}"
    if mid in (31, 32, 33, 34):
        return f"{_NAMES[mid].replace('Home', home).replace('Away', away)} — {outcome.lower()}"
    if mid in (546, 547, 37, 36):
        return f"{sub(outcome).replace('/', ' or ')}"
    if mid in (25, 548, 21):
        return f"{_NAMES[mid]} {outcome}"
    if mid == 60:      # first-half result markets (engine/half.py)
        return {"Home": f"{home} to lead at half-time", "Away": f"{away} to lead at half-time"
                }.get(outcome, "Level at half-time")
    if mid == 63:
        return {"Home or Draw": f"{home} or level at half-time",
                "Draw or Away": f"{away} or level at half-time",
                "Home or Away": f"{home} or {away} to lead at half-time"}.get(outcome, outcome)
    if mid == 64:
        return f"{sub(outcome)} at half-time (draw no bet)"
    return f"{_NAMES.get(mid, 'Market')}: {sub(outcome)}"


def ladder(raw_markets: list[dict]) -> list[tuple[str, float, Rule]]:
    """[(key, price, rule)] for every supported, priced outcome in a raw
    SportyBet market list ({id, desc, specifier, outcomes:[{id, desc, odds}]})."""
    out = []
    for m in raw_markets or []:
        try:
            mid = int(m.get("id"))
        except (TypeError, ValueError):
            continue
        if mid not in LADDER_MARKET_IDS:
            continue
        spec = m.get("specifier") or ""
        for o in m.get("outcomes", []):
            try:
                price = float(o.get("odds"))
            except (TypeError, ValueError):
                continue
            if price <= 1.0:
                continue
            r = rule_for(mid, spec, o.get("desc") or "")
            if r is not None:
                out.append((key(mid, spec, o.get("desc") or ""), price, r))
    return out
