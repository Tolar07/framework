"""
ICE HOCKEY GOALS MODEL (standing order 50, multi-sport rollout; Architect 2026-11-05).

Hockey is a low-scoring game like football, so the football approach carries over: each team
gets an attack and a defence rating from its REGULATION (60-minute) goals, recent games weighted
more (half-life HALF_LIFE days), shrunk toward the league average (PRIOR_GAMES pseudo-games),
plus a home edge. Goals in 60 minutes ~ independent Poisson(lambda_home), Poisson(lambda_away).

From the score grid every SportyBet ice hockey market is priced:
  1    1X2 (regular time)            H / D / A after 60 minutes
  406  winner incl. OT and penalties regulation win, or a level game won in OT/SO
  410  handicap incl. OT and penalties a level game is decided by one goal (OT/SO)
  18   over/under (regular time)
  16   Asian handicap (regular time), half lines only
  14   3-way handicap a:b (regular time)
  29   GG/NG (regular time)
OT_HOME = share of level games the home side wins in OT/SO, fitted from the data.

NHL only (data/nhl_source.py). Other leagues are priced from the Matchbook exchange's fair
chance (engine/ice_hockey.py). backtest/hockey_backtest.py tests it walk-forward.
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from data import nhl_source as nhl

HALF_LIFE = 365.0     # days (chosen in backtest/ICE_HOCKEY_STUDY.md, 9 tries)
PRIOR_GAMES = 8.0     # shrinkage toward the league average
MAX_GOALS = 12
ITERATIONS = 25
DRAW_BOOST = 1.3    # x the level-score cells after 60 min (Poisson under-rates hockey draws); set from backtest/ICE_HOCKEY_STUDY.md


def _days(a: str, b: str) -> float:
    fa = datetime.fromisoformat(a.replace("Z", "+00:00"))
    fb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return (fb - fa).total_seconds() / 86400.0


class Model:
    def __init__(self, att: dict, dfn: dict, mu_home: float, mu_away: float, ot_home: float, n: int,
                 draw_boost: float | None = None):
        self.att, self.dfn = att, dfn
        self.draw_boost = DRAW_BOOST if draw_boost is None else draw_boost
        self.mu_home, self.mu_away, self.ot_home, self.n = mu_home, mu_away, ot_home, n

    def knows(self, home: str, away: str) -> bool:
        return home in self.att and away in self.att

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        return (self.mu_home * self.att.get(home, 1.0) * self.dfn.get(away, 1.0),
                self.mu_away * self.att.get(away, 1.0) * self.dfn.get(home, 1.0))

    def grid(self, home: str, away: str) -> list[list[float]]:
        lh, la = self.lambdas(home, away)
        ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(MAX_GOALS + 1)]
        pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(MAX_GOALS + 1)]
        g = [[ph[i] * pa[j] * (self.draw_boost if i == j else 1.0) for j in range(MAX_GOALS + 1)]
             for i in range(MAX_GOALS + 1)]
        s = sum(map(sum, g))
        return [[x / s for x in row] for row in g]


def fit(games: list[dict], as_of: str, half_life: float = HALF_LIFE, prior: float = PRIOR_GAMES) -> Model | None:
    """Ratings from every game that started before as_of (ISO time)."""
    rows = [g for g in games if g.get("ko") and g["ko"] < as_of]
    if len(rows) < 50:
        return None
    w, hs, as_ = [], [], []
    for g in rows:
        h, a = nhl.reg_score(g)
        w.append(0.5 ** (_days(g["ko"], as_of) / half_life))
        hs.append(h)
        as_.append(a)
    tw = sum(w)
    mu_h = sum(wi * h for wi, h in zip(w, hs)) / tw
    mu_a = sum(wi * a for wi, a in zip(w, as_)) / tw
    teams = sorted({g["home"] for g in rows} | {g["away"] for g in rows})
    att = dict.fromkeys(teams, 1.0)
    dfn = dict.fromkeys(teams, 1.0)
    for _ in range(ITERATIONS):
        num = dict.fromkeys(teams, prior)
        den = dict.fromkeys(teams, prior)
        for wi, g, h, a in zip(w, rows, hs, as_):
            num[g["home"]] += wi * h
            den[g["home"]] += wi * mu_h * dfn[g["away"]]
            num[g["away"]] += wi * a
            den[g["away"]] += wi * mu_a * dfn[g["home"]]
        att = {t: num[t] / den[t] for t in teams}
        num = dict.fromkeys(teams, prior)
        den = dict.fromkeys(teams, prior)
        for wi, g, h, a in zip(w, rows, hs, as_):
            num[g["home"]] += wi * a
            den[g["home"]] += wi * mu_a * att[g["away"]]
            num[g["away"]] += wi * h
            den[g["away"]] += wi * mu_h * att[g["home"]]
        dfn = {t: num[t] / den[t] for t in teams}
    ot = [(wi, g["hs"] > g["as"]) for wi, g in zip(w, rows) if g.get("period") in ("OT", "SO")]
    ot_home = (sum(wi for wi, won in ot if won) + 5) / (sum(wi for wi, _ in ot) + 10) if ot else 0.5
    return Model(att, dfn, mu_h, mu_a, ot_home, len(rows))


# ── markets from the grid ───────────────────────────────────────────────────────────────────
def _margins(grid: list[list[float]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for i, row in enumerate(grid):
        for j, p in enumerate(row):
            out[i - j] = out.get(i - j, 0.0) + p
    return out


def _num(spec: str, key: str) -> float | None:
    m = re.search(rf"{key}=([+-]?\d+(?:\.\d+)?)", spec or "")
    return float(m.group(1)) if m else None


def chance(market_id: str, spec: str, outcome: str, grid: list[list[float]], ot_home: float) -> float | None:
    """The model's chance that one SportyBet side wins. None = not a market this model prices
    (or a whole line that can push)."""
    o = (outcome or "").strip()
    ol = o.lower()
    mg = _margins(grid)
    p_h = sum(p for m, p in mg.items() if m > 0)
    p_d = mg.get(0, 0.0)
    p_a = sum(p for m, p in mg.items() if m < 0)
    if market_id == "1":
        return {"home": p_h, "draw": p_d, "away": p_a}.get(ol)
    if market_id == "406":
        return {"home": p_h + p_d * ot_home, "away": p_a + p_d * (1 - ot_home)}.get(ol)
    if market_id in ("18",):
        line = _num(spec, "total")
        if line is None or line % 1 != 0.5:
            return None
        over = sum(p for i, row in enumerate(grid) for j, p in enumerate(row) if i + j > line)
        return over if ol.startswith("over") else 1 - over if ol.startswith("under") else None
    if market_id in ("16", "410"):
        mm = re.fullmatch(r"(home|away) \(([+-]?\d+(?:\.\d+)?)\)", ol)
        if not mm:
            return None
        side, line = mm.group(1), float(mm.group(2))
        if line % 1 != 0.5:
            return None
        sign = 1 if side == "home" else -1
        p = 0.0
        for m, pm in mg.items():
            if m != 0 or market_id == "16":
                p += pm if sign * m + line > 0 else 0.0
            else:   # level after 60: OT/SO decides by one goal
                win = ot_home if side == "home" else 1 - ot_home
                p += pm * (win * (1 + line > 0) + (1 - win) * (-1 + line > 0))
        return p
    if market_id == "14":
        mm = re.fullmatch(r"(home|draw|away) \((\d+):(\d+)\)", ol)
        if not mm:
            return None
        shift = int(mm.group(2)) - int(mm.group(3))
        res = {"home": lambda m: m + shift > 0, "draw": lambda m: m + shift == 0, "away": lambda m: m + shift < 0}
        return sum(p for m, p in mg.items() if res[mm.group(1)](m))
    if market_id == "29":
        p0h = sum(grid[0])
        p0a = sum(row[0] for row in grid)
        gg = 1 - p0h - p0a + grid[0][0]
        return gg if ol == "yes" else 1 - gg if ol == "no" else None
    return None


def settle(market_id: str, spec: str, outcome: str, reg: tuple[int, int], final: tuple[int, int]) -> int | None:
    """1 won / 0 lost / None void-or-unknown, from the regulation and final scores."""
    o = (outcome or "").strip().lower()
    rh, ra = reg
    fh, fa = final
    if market_id == "1":
        res = "home" if rh > ra else "away" if ra > rh else "draw"
        return int(o == res)
    if market_id == "406":
        if fh == fa:
            return None
        return int(o == ("home" if fh > fa else "away"))
    if market_id == "18":
        line = _num(spec, "total")
        if line is None or rh + ra == line:
            return None
        return int((rh + ra > line) == o.startswith("over"))
    if market_id in ("16", "410"):
        mm = re.fullmatch(r"(home|away) \(([+-]?\d+(?:\.\d+)?)\)", o)
        if not mm:
            return None
        h, a = (rh, ra) if market_id == "16" else (fh, fa)
        m = (h - a) if mm.group(1) == "home" else (a - h)
        v = m + float(mm.group(2))
        return None if v == 0 else int(v > 0)
    if market_id == "14":
        mm = re.fullmatch(r"(home|draw|away) \((\d+):(\d+)\)", o)
        if not mm:
            return None
        m = rh - ra + int(mm.group(2)) - int(mm.group(3))
        res = "home" if m > 0 else "away" if m < 0 else "draw"
        return int(mm.group(1) == res)
    if market_id == "29":
        gg = rh > 0 and ra > 0
        return int(gg == (o == "yes"))
    return None
