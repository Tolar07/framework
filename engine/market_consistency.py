"""
MARKET CONSISTENCY — to-do #7 idea 1 (RECORDED ONLY, changes no stake, no threshold, no pick).

SportyBet prices one game in many markets. Each one implies the expected goals of the game,
and a book that sets them separately leaves some lines out of step with the rest. This fits ONE
Dixon-Coles scoreline grid (two Poisson rates + the low-score rho) to all of SportyBet's own
de-vigged prices at once — 1X2, every Over/Under line it quotes (1.5 / 2.5 / 3.5) and BTTS — and
reprices every side of every market from that grid:

    model_win, model_push   the side's chance under the joint grid (engine.full_markets rules)
    ev                      model_win * price + model_push - 1: how soft (> 0) or hard (< 0)
                            the side is against the book's own other markets

Markets are yes/no: both sides of every main market are recorded, and a ladder market is kept
only with every outcome of the same line, so the soft side is always read beside its other side.

engine.full_markets.market_matrix already fits 1X2 + O/U 2.5 (independent Poisson) for the
LINE CONSISTENCY GUARD, which only drops a stale line. This uses every line and BTTS, adds rho,
and records the numbers so backtest/market_consistency_study.py can measure them on graded games
(flat return and closing-line value, thresholds chosen on the earlier half, verdict on the later).

Where it writes: monitor/universe_sweep.py attaches row["xm"] = {"first": ..., "last": ...} to
every graded football game before it is archived to data/universe/. Nothing reads it to pick or
stake; wiring it into stakes needs the Architect's OK after out-of-sample gains.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from engine import full_markets as fm

MAX_G = fm.MAX_G
_G = np.arange(MAX_G + 1)
TOT = fm.H_GRID + fm.A_GRID
RHO_BOUNDS = (-0.2, 0.1)
LAMBDA_BOUNDS = (0.15, 4.5)
OU_LINES = ("1.5", "2.5", "3.5")
DC_SIDES = ("1x", "12", "x2")          # universe order of p["dc"]
LADDER_EV_KEEP = 0.0                   # a ladder line is kept when one of its sides has ev > this


def _devig(prices) -> list[float] | None:
    try:
        inv = [1 / float(p) for p in prices]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    s = sum(inv)
    if not all(x > 0 for x in inv) or not 1.0 <= s <= 1.4:
        return None
    return [x / s for x in inv]


def grid(lh: float, la: float, rho: float) -> np.ndarray:
    m = np.outer(poisson.pmf(_G, lh), poisson.pmf(_G, la))
    m[0, 0] *= 1 - lh * la * rho
    m[0, 1] *= 1 + lh * rho
    m[1, 0] *= 1 + la * rho
    m[1, 1] *= 1 - rho
    m = np.clip(m, 0.0, None)
    return m / m.sum()


def _targets(p: dict) -> list[tuple[str, float]]:
    """(statistic, de-vigged chance) pairs the grid is fitted to."""
    out: list[tuple[str, float]] = []
    x = _devig(p.get("1x2") or [])
    if x and len(x) == 3:
        out += [("home", x[0]), ("draw", x[1]), ("away", x[2])]
    for line in OU_LINES:
        x = _devig(p.get(f"ou{line}") or [])
        if x and len(x) == 2:
            out.append((f"over{line}", x[0]))
    x = _devig(p.get("btts") or [])
    if x and len(x) == 2:
        out.append(("btts", x[0]))
    return out


def _stat(m: np.ndarray, name: str) -> float:
    if name == "home":
        return float(np.tril(m, -1).sum())
    if name == "away":
        return float(np.triu(m, 1).sum())
    if name == "draw":
        return float(np.trace(m))
    if name == "btts":
        return float(1 - m[0, :].sum() - m[:, 0].sum() + m[0, 0])
    return float(m[float(name[4:]) < TOT].sum())          # overN.5


def fit(p: dict) -> dict | None:
    """The joint grid for one game's price dict (universe p). None unless 1X2 and at least one
    goals market are quoted — 1X2 alone cannot say anything about the totals."""
    t = _targets(p)
    names = [n for n, _ in t]
    if not {"home", "draw", "away"} <= set(names) or len(t) < 4:
        return None
    want = np.array([v for _, v in t])

    def unpack(x):
        lo, hi = math.log(LAMBDA_BOUNDS[0]), math.log(LAMBDA_BOUNDS[1])
        lh = math.exp(min(max(x[0], lo), hi))
        la = math.exp(min(max(x[1], lo), hi))
        rho = RHO_BOUNDS[0] + (RHO_BOUNDS[1] - RHO_BOUNDS[0]) / (1 + math.exp(-min(max(x[2], -30), 30)))
        return lh, la, rho

    def loss(x):
        m = grid(*unpack(x))
        return float(((np.array([_stat(m, n) for n in names]) - want) ** 2).sum())

    res = minimize(loss, x0=[math.log(1.4), math.log(1.1), 0.0], method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-10, "maxiter": 600})
    lh, la, rho = unpack(res.x)
    return {"lh": round(lh, 3), "la": round(la, 3), "rho": round(rho, 3),
            "rmse": round(math.sqrt(res.fun / len(t)), 4), "n": len(t), "matrix": grid(lh, la, rho)}


def _main_sides(p: dict) -> list[tuple[str, float, fm.Rule]]:
    b = fm._b
    sides: list[tuple[str, float, fm.Rule]] = []
    x = p.get("1x2") or []
    if len(x) == 3:
        sides += [("1x2:home", x[0], lambda h, a: b(h > a)), ("1x2:draw", x[1], lambda h, a: b(h == a)),
                  ("1x2:away", x[2], lambda h, a: b(h < a))]
    for line in OU_LINES:
        x = p.get(f"ou{line}") or []
        if len(x) == 2:
            n = float(line)
            sides += [(f"ou{line}:over", x[0], lambda h, a, n=n: b(h + a > n)),
                      (f"ou{line}:under", x[1], lambda h, a, n=n: b(h + a < n))]
    x = p.get("btts") or []
    if len(x) == 2:
        sides += [("btts:yes", x[0], lambda h, a: b(h > 0 and a > 0)),
                  ("btts:no", x[1], lambda h, a: b(h == 0 or a == 0))]
    x = p.get("dc") or []
    if len(x) == 3:
        sides += [("dc:1x", x[0], lambda h, a: b(h >= a)), ("dc:12", x[1], lambda h, a: b(h != a)),
                  ("dc:x2", x[2], lambda h, a: b(h <= a))]
    return [(k, float(pr), r) for k, pr, r in sides if pr and float(pr) > 1]


def _side(m: np.ndarray, price: float, rule: fm.Rule) -> list[float]:
    win, push = fm.evaluate(m, rule)
    return [round(win, 4), round(push, 4), round(win * price + push - 1, 4)]


def summary(p: dict | None, ladder: bool = True) -> dict | None:
    """Compact record for one look: the fit plus [model_win, model_push, ev] per side. Every
    main-market side is kept; a ladder line (market id + specifier) is kept with all its outcomes
    when any one of them has ev > LADDER_EV_KEEP."""
    if not isinstance(p, dict):
        return None
    f = fit(p)
    if f is None:
        return None
    m = f.pop("matrix")
    out = dict(f)
    out["sides"] = {k: _side(m, pr, r) for k, pr, r in _main_sides(p)}
    if ladder and isinstance(p.get("ladder"), dict):
        lines: dict[str, dict[str, list[float]]] = {}
        for k, pr in p["ladder"].items():
            parsed = fm.parse_key(k)
            if not parsed or not pr or float(pr) <= 1:
                continue
            rule = fm.rule_for(*parsed)
            if rule is None:
                continue
            lines.setdefault(f"{parsed[0]}|{parsed[1]}", {})[k] = _side(m, float(pr), rule)
        out["ladder"] = {k: v for line in lines.values() if max(s[2] for s in line.values()) > LADDER_EV_KEEP
                         for k, v in line.items()}
    return out


def attach(rows: list[dict]) -> str:
    """Record row["xm"] on every graded football game (first and last look). Never raises."""
    done = 0
    for r in rows:
        if r.get("sport") != "football" or "xm" in r:
            continue
        try:
            xm = {w: summary((r.get(w) or {}).get("p")) for w in ("first", "last")}
        except Exception:  # noqa: BLE001, S112 — a bad price dict never stops the archive
            continue
        if xm["first"] or xm["last"]:
            r["xm"] = xm
            done += 1
    return f"consistency recorded {done}"


def side_of(xm_look: dict | None, key: str) -> list[float] | None:
    """[model_win, model_push, ev] for a side key ("1x2:home", "SB:18|total=1.5|Over 1.5")."""
    if not xm_look:
        return None
    return (xm_look.get("sides") or {}).get(key) or (xm_look.get("ladder") or {}).get(key)
