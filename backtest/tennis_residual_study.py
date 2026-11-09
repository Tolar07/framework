"""
TENNIS residual study: does anything add to Pinnacle's close? (framework#345, record-only shadow)

A logistic model with the de-vigged Pinnacle close as a FIXED offset (coefficient 1, so with no signal it equals the
market) and two candidate signals: the Elo gap (overall + surface mix, from tennis_backtest.replay) and the log
ranking ratio. It is refit each test year on EARLIER years only (walk-forward; ridge-shrunk toward 'the market is
right'), so the held-out years never inform their own fit. Also a calibration table of the close by price bucket
(favourite-longshot check). Side orientation is by name (see tennis_backtest.parse); a missing rank reads PENDING
(the row is skipped for the model, never invented). Nothing here changes a stake, bar, threshold or live switch.

  python backtest/tennis_residual_study.py      writes backtest/TENNIS_RESIDUAL_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_RESIDUAL_STUDY.md"
FIRST_TEST = 2022          # test years 2022.. ; each fit uses only earlier years
RIDGE = 50.0               # shrink toward 'market is right'
BUCKETS = ((0.0, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.85), (0.85, 1.01))


def features(games: list[dict]) -> list[list[float] | None]:
    """[Elo-gap logit, log rank ratio] per match, None when either is not available before the match."""
    el = tb.replay(games, 32.0, 0.5)
    out = []
    for g, e in zip(games, el):
        if e is None or not g.get("ra") or not g.get("rb") or g["ra"] <= 0 or g["rb"] <= 0:
            out.append(None)
            continue
        out.append([tb.logit(e), math.log(g["rb"] / g["ra"])])
    return out


def solve(a: list[list[float]], v: list[float]) -> list[float] | None:
    n = len(v)
    m = [row[:] + [v[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-12:
            return None
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                for j in range(c, n + 1):
                    m[r][j] -= f * m[c][j]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit(rows: list[tuple[list[float], float, float]], iters: int = 25) -> list[float]:
    """Newton fit of beta in P = sig(offset + x.beta) with a ridge pull to 0 (rows: x, offset, y)."""
    k = len(rows[0][0]) if rows else 0
    b = [0.0] * k
    for _ in range(iters):
        grad = [-RIDGE * v for v in b]
        hess = [[RIDGE if i == j else 0.0 for j in range(k)] for i in range(k)]
        for x, off, y in rows:
            p = tb.sig(off + sum(bi * xi for bi, xi in zip(b, x)))
            w = p * (1 - p)
            for i in range(k):
                grad[i] += (y - p) * x[i]
                for j in range(k):
                    hess[i][j] += w * x[i] * x[j]
        step = solve(hess, grad)
        if step is None:
            break
        b = [bi + si for bi, si in zip(b, step)]
        if max(abs(s) for s in step) < 1e-7:
            break
    return b


def walk_forward(games: list[dict], feats: list) -> tuple[list[dict], dict]:
    """Per held-out match: model chance (offset + signals). Returns rows and the coefficients by year."""
    last = max(g["year"] for g in games)
    rows, coefs = [], {}
    for year in range(FIRST_TEST, last + 1):
        train = [(f, tb.logit(g["mkt"]), g["y"]) for g, f in zip(games, feats) if f and g["year"] < year]
        if len(train) < 1000:
            continue
        beta = fit(train)
        coefs[year] = beta
        for g, f in zip(games, feats):
            if f and g["year"] == year:
                rows.append({"g": g, "q": tb.sig(tb.logit(g["mkt"]) + sum(b * x for b, x in zip(beta, f)))})
    return rows, coefs


def _nll(p: float, y: float) -> float:
    return -math.log(p if y else 1 - p)


def score(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0}
    return {"n": n, "ll": sum(_nll(r["q"], r["g"]["y"]) for r in rows) / n,
            "mkt_ll": sum(_nll(r["g"]["mkt"], r["g"]["y"]) for r in rows) / n}


def paired_se(rows: list[dict]) -> float | None:
    """Standard error of the mean per-match log-loss gain (market minus model)."""
    d = [_nll(r["g"]["mkt"], r["g"]["y"]) - _nll(r["q"], r["g"]["y"]) for r in rows]
    if len(d) < 2:
        return None
    m = sum(d) / len(d)
    return math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1) / len(d))


def calibration(games: list[dict]) -> list[tuple]:
    """Both sides of every match: de-vigged close vs how often that side won, and ROI at the average close."""
    out = []
    for lo, hi in BUCKETS:
        n = bets = 0
        won = pm = pnl = 0.0
        for g in games:
            for p, win, price in ((g["mkt"], g["y"] == 1.0, g["qa"]), (1 - g["mkt"], g["y"] == 0.0, g["qb"])):
                if lo <= p < hi:
                    n += 1
                    won += win
                    pm += p
                    if price:
                        bets += 1
                        pnl += (price - 1) if win else -1.0
        out.append((lo, hi, n, pm / n if n else None, won / n if n else None, pnl / bets if bets else None))
    return out


def run(games: list[dict]) -> str:
    rows, coefs = walk_forward(games, features(games))
    sc = score(rows)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis residual study (shadow, record only)", "",
         f"Made {made} by `backtest/tennis_residual_study.py` (framework#345). Pinnacle's de-vigged close is a fixed "
         f"offset; signals are the Elo gap and the log rank ratio; coefficients refit each year on earlier years only "
         f"(ridge {RIDGE:g}). Tries counted: **1** model (2 signals, one ridge value, no search).", ""]
    if not sc["n"]:
        L.append("PENDING: not enough matches with Elo and ranks to fit.")
        return "\n".join(L) + "\n"
    se = paired_se(rows) or 0.0
    gain = sc["mkt_ll"] - sc["ll"]
    ys = [r["g"]["year"] for r in rows]
    L += ["| Held-out years | Matches | Model log loss | Pinnacle close log loss | Gain per match | Std error |",
          "|---|---|---|---|---|---|",
          f"| {min(ys)}-{max(ys)} | {sc['n']} | {sc['ll']:.5f} | {sc['mkt_ll']:.5f} | {gain:+.5f} | {se:.5f} |", "",
          "| Fit for year | Elo-gap coefficient | Log-rank-ratio coefficient |", "|---|---|---|"]
    for y, b in sorted(coefs.items()):
        L.append(f"| {y} | {b[0]:+.4f} | {b[1]:+.4f} |")
    L += ["", "## Calibration of the Pinnacle close (all matches, both sides)", "",
          "| De-vigged close | Sides | Mean close | Won | ROI at average close |", "|---|---|---|---|---|"]
    for lo, hi, n, pm, w, roi in calibration(games):
        if n:
            L.append(f"| {lo:.2f}-{min(hi, 1.0):.2f} | {n} | {pm:.3f} | {w:.3f} | "
                     + (f"{roi:+.1%}" if roi is not None else "PENDING") + " |")
    z = gain / se if se else 0.0
    L += ["", "## Reading", "",
          f"- Gain {gain:+.5f} log loss per match ({z:+.1f} standard errors): "
          + ("a signal beyond the price, worth a closer shadow." if z >= 2 else
             "not distinguishable from zero; the price already holds this. Keep pricing off the exchange."),
          "- 'Won' near 'Mean close' in every bucket means the close is calibrated; a gap is a favourite-longshot bias.",
          "- Bookmaker average prices carry a margin; exchange commission is not modelled.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = tb.load()
    if len(games) < 3000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
