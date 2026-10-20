"""
WALK-FORWARD TESTS shared by backtest/features_study.py and the research
harness (research/runner.py), 2026-10-20.

feature_test — does a feature add information to the model's own chance?
    Day by day: fit  logit(y) = logit(p_model) + b * z(feature)  on every
    EARLIER day only, predict the day, score both the model alone and the
    model + feature (Brier) on the same rows. The model's number is the
    offset, so the test is "beyond what the model already knew".

bet_test — does a betting rule make money and beat the close?
    The rule's bets in date order, entry at the first price; return per unit
    staked ± its standard error, closing-line value (first / last - 1), and the
    same split into the earlier and the later half — a rule that only worked
    in the half it was thought up on is not evidence.

Pure functions; no data is read here.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

MIN_TRAIN = 40          # rows with the feature before a day is scored
RIDGE = 2.0


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-max(min(x, 30), -30)))


def fit_offset(rows: list[tuple[float, int, float]]) -> float:
    """b of logit(y) = logit(p) + b*x by Newton with a ridge (x pre-scaled)."""
    b = 0.0
    for _ in range(25):
        g, h = -RIDGE * b, RIDGE
        for p, y, x in rows:
            q = _sig(_logit(p) + b * x)
            g += (y - q) * x
            h += q * (1 - q) * x * x
        step = g / h
        b += step
        if abs(step) < 1e-6:
            break
    return b


def _mean_se(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(v / n)


def feature_test(rows: Iterable[tuple[str, float, int, float | None]]) -> dict[str, Any]:
    """rows: (day, model chance, outcome 0/1, feature or None)."""
    have = sorted((d, p, y, f) for d, p, y, f in rows if isinstance(f, (int, float)))
    days = sorted({d for d, *_ in have})
    gains: list[float] = []
    base_b: list[float] = []
    coef = None
    for d in days:
        train = [(p, y, f) for dd, p, y, f in have if dd < d]
        if len(train) < MIN_TRAIN:
            continue
        mu = sum(f for *_, f in train) / len(train)
        sd = math.sqrt(sum((f - mu) ** 2 for *_, f in train) / len(train)) or 1.0
        coef = fit_offset([(p, y, (f - mu) / sd) for p, y, f in train])
        for dd, p, y, f in have:
            if dd != d:
                continue
            q = _sig(_logit(p) + coef * (f - mu) / sd)
            bm, bf = (p - y) ** 2, (q - y) ** 2
            base_b.append(bm)
            gains.append(bm - bf)                 # positive: the feature helped
    m, se = _mean_se(gains)
    n = len(gains)
    if n < 100:
        verdict = "NOT ENOUGH DATA"
    elif m > 2 * se:
        verdict = "ADDS INFORMATION"
    elif m < -2 * se:
        verdict = "HURTS"
    else:
        verdict = "NO CLEAR EFFECT"
    return {"rows": len(have), "scored": n, "brier_model": round(sum(base_b) / n, 4) if n else None,
            "gain": round(m, 5), "se": round(se, 5), "last_coef": None if coef is None else round(coef, 3),
            "verdict": verdict}


def _half(bets: list[tuple[str, int, float, float | None]]) -> dict[str, Any]:
    rets = [(px - 1) if won else -1.0 for _, won, px, _ in bets]
    clv = [px / last - 1 for _, _, px, last in bets if last and last > 1]
    m, se = _mean_se(rets)
    c, cse = _mean_se(clv)
    return {"n": len(bets), "hit": round(sum(w for _, w, _, _ in bets) / len(bets), 3) if bets else None,
            "roi": round(m, 4), "roi_se": round(se, 4),
            "clv": round(c, 4) if clv else None, "clv_se": round(cse, 4) if clv else None}


def bet_test(bets: Iterable[tuple[str, int, float, float | None]], min_n: int = 60) -> dict[str, Any]:
    """bets: (day, won 0/1, price taken, last price before kick-off or None)."""
    b = sorted(bets)
    mid = len(b) // 2
    out: dict[str, Any] = {"all": _half(b), "early": _half(b[:mid]), "late": _half(b[mid:])}
    late = out["late"]
    if len(b) < min_n:
        out["verdict"] = "NOT ENOUGH DATA"
    elif (out["early"]["roi"] > 0 and late["roi"] > 0 and (late["clv"] or 0) > 0):
        out["verdict"] = "ACCEPT AS SHADOW"
    elif late["roi"] < -late["roi_se"] or (late["clv"] is not None and late["clv"] < 0 and late["roi"] < 0):
        out["verdict"] = "REJECT"
    else:
        out["verdict"] = "INCONCLUSIVE"
    return out
