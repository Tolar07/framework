"""
RESIDUAL MODEL — step 6 of the edge plan (Architect 2026-11-04). RECORDED ONLY.

The old target was "does the pick win?". The market already answers that as well as we can
(backtest/BOTH_SIDES_STUDY.md), so a model trained on it learns the price back. This model
starts FROM the exchange's fair chance and learns only what the exchange misses:

    logit P(won) = logit(exchange chance at the look) + w . features

so a feature earns weight only when it moves results away from the exchange's own chance.
Ridge-penalised (RIDGE), judged WALK-FORWARD by day: each day is scored with weights fitted
only on the days before it, against the exchange chance alone (log loss, lower = better).
A positive gain that is more than 2 standard errors is information the price did not have.

Features (all known when the bet could be placed):
    gap        log(SportyBet price x exchange chance): SportyBet above / below fair
    basketball 1 for basketball sides
    fam:<id>   the SportyBet market id (top families only)
    band:<b>   SportyBet price band
    early      first seen 24 h+ before kick-off
    model      board picks only: logit(the framework's chance) - logit(exchange chance)
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

RIDGE = 4.0
MIN_TRAIN = 200
BANDS = ((1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 3.0), (3.0, 99.0))
TOP_FAMILIES = 8


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def family(key: str) -> str:
    return key.split("|", 1)[0]


def features(r: dict, fams: list[str]) -> dict[str, float]:
    s, p = r["price"], r["p"]
    f = {"gap": math.log(s * p), "basketball": 1.0 if r.get("sport") == "basketball" else 0.0,
         "early": 1.0 if (r.get("h") or 0) >= 24 else 0.0}
    fam = family(r["key"])
    for k in fams:
        f[f"fam:{k}"] = 1.0 if fam == k else 0.0
    for lo, hi in BANDS:
        f[f"band:{lo:g}-{hi:g}"] = 1.0 if lo <= s < hi else 0.0
    if r.get("model") is not None:
        f["model"] = _logit(r["model"]) - _logit(p)
    return f


def fit(X: np.ndarray, y: np.ndarray, off: np.ndarray, ridge: float = RIDGE, iters: int = 30) -> np.ndarray:
    """Ridge logistic regression with a fixed offset (Newton's method)."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        z = np.clip(off + X @ w, -30, 30)
        mu = 1 / (1 + np.exp(-z))
        g = X.T @ (mu - y) + ridge * w
        H = (X * (mu * (1 - mu))[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-6:
            break
    return w


def _ll(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -30, 30)
    return np.logaddexp(0, z) - y * z          # per-row log loss


def study(rows: list[dict], name: str) -> dict:
    """rows: {day, key, sport, price, p (exchange chance at the look), won, h?, model?}."""
    rows = [r for r in rows if r.get("p") and 0 < r["p"] < 1 and r.get("price") and r.get("won") in (0, 1)]
    out: dict = {"name": name, "n": len(rows)}
    if len(rows) < MIN_TRAIN:
        out["status"] = f"COLLECTING ({len(rows)} of {MIN_TRAIN} graded rows)"
        return out
    fams = [k for k, _ in Counter(family(r["key"]) for r in rows).most_common(TOP_FAMILIES)]
    names = sorted(features(rows[0], fams))
    if any(r.get("model") is not None for r in rows):
        names = sorted(set(names) | {"model"})
    X = np.array([[features(r, fams).get(k, 0.0) for k in names] for r in rows])
    y = np.array([float(r["won"]) for r in rows])
    off = np.array([_logit(r["p"]) for r in rows])
    days = np.array([r["day"] for r in rows])
    gains = []
    for d in sorted(set(days)):
        tr, te = days < d, days == d
        if tr.sum() < MIN_TRAIN:
            continue
        w = fit(X[tr], y[tr], off[tr])
        gains += list(_ll(y[te], off[te]) - _ll(y[te], off[te] + X[te] @ w))
    w = fit(X, y, off)
    out["weights"] = {k: round(float(v), 4) for k, v in zip(names, w, strict=True)}
    out["exchange_logloss"] = round(float(_ll(y, off).mean()), 5)
    if gains:
        g = np.array(gains)
        se = float(g.std(ddof=1) / math.sqrt(len(g))) if len(g) > 1 else float("nan")
        out["walk_forward"] = {"n": len(g), "gain": round(float(g.mean()), 5), "se": round(se, 5)}
        beats = len(g) > 1 and g.mean() > 2 * se
        out["status"] = ("BEATS THE EXCHANGE (out of sample) — Architect review" if beats
                         else "no information beyond the exchange yet")
    else:
        out["status"] = "fitted, waiting for a day to test out of sample"
    return out
