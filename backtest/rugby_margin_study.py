"""
RUGBY winning-margin walk-forward study (framework#344, record-only; also feeds #384).

Handicap and margin-band markets need the MARGIN, not just the winner. Same ESPN games as backtest/rugby_backtest.py,
replayed in date order. Model: rating-based expected home margin
    mu = running mean home margin + scale * (r_home - r_away) ; ratings move by lr * (margin - mu)
Score = mean absolute error of mu vs the real margin, against the baseline "running mean home margin", and the
empirical split of winning margins into bands (1-7, 8-14, 15+). Every setting tried is counted; the best is chosen
on 2014-2019 and reported on 2020+ only. Record only: nothing here changes a stake, bar, threshold or live switch.

  python backtest/rugby_margin_study.py      writes backtest/RUGBY_MARGIN_STUDY.md
"""
from __future__ import annotations

import itertools
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_MARGIN_STUDY.md"
LRS = (0.02, 0.05, 0.10)
SCALES = (0.5, 1.0)
MIN_GAMES = 100
BANDS = (("1-7", 1, 7), ("8-14", 8, 14), ("15+", 15, 10**6))


def replay(games: list[dict], lr: float, scale: float) -> list[tuple[float, float] | None]:
    """(predicted home margin, baseline running-mean home margin) BEFORE each game; None while data is thin."""
    rating = defaultdict(float)
    m_sum, m_n, out = 0.0, 0, []
    for g in games:
        h, a = g["home"], g["away"]
        base = m_sum / m_n if m_n else 0.0
        mu = base + scale * (rating[h] - rating[a])
        out.append((mu, base) if m_n >= MIN_GAMES else None)
        err = (g["hs"] - g["as"]) - mu
        rating[h] += lr * err
        rating[a] -= lr * err
        m_sum, m_n = m_sum + (g["hs"] - g["as"]), m_n + 1
    return out


def evaluate(games, preds, years) -> dict:
    n, e, e0 = 0, 0.0, 0.0
    for g, p in zip(games, preds):
        if p is None or not (years[0] <= g["year"] <= years[1]):
            continue
        m = g["hs"] - g["as"]
        n += 1
        e += abs(p[0] - m)
        e0 += abs(p[1] - m)
    return {"n": n, "mae": e / n if n else None, "base": e0 / n if n else None}


def bands(games, years) -> dict:
    """Share of decided games whose winner won by each band, in the given years."""
    c, tot = {b[0]: 0 for b in BANDS}, 0
    for g in games:
        m = abs(g["hs"] - g["as"])
        if m == 0 or not (years[0] <= g["year"] <= years[1]):
            continue
        tot += 1
        for name, lo, hi in BANDS:
            if lo <= m <= hi:
                c[name] += 1
    return {"n": tot, **{k: (v / tot if tot else None) for k, v in c.items()}}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    cache = {(lr, s): replay(games, lr, s) for lr, s in itertools.product(LRS, SCALES)}
    tuned = {k: evaluate(games, p, rb.TUNE_YEARS) for k, p in cache.items()}
    ok = {k: t for k, t in tuned.items() if t["n"] >= MIN_GAMES}
    best = min(ok, key=lambda k: ok[k]["mae"]) if ok else None
    held = evaluate(games, cache[best], test) if best else None
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby winning-margin walk-forward study", "",
         f"Made {made} by `backtest/rugby_margin_study.py` (framework#344, #384). {len(games)} games, final "
         f"scores only (ESPN). Settings tried: **{len(cache)}** (learning rate x scale); chosen on "
         f"{rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**.", ""]
    if not held or not held["n"]:
        L.append("PENDING: not enough games to grade a margin model.")
        return "\n".join(L) + "\n"
    L += ["| Rule (held-out years) | Games | Mean abs error of margin (points) |", "|---|---|---|",
          f"| Baseline: running mean home margin | {held['n']} | {held['base']:.2f} |",
          f"| Best on tuning years: lr {best[0]}, scale {best[1]} | {held['n']} | {held['mae']:.2f} |", ""]
    b = bands(games, test)
    L += [f"Winning margin bands, held-out years ({b['n']} decided games): " +
          ", ".join(f"{n} pts {b[n]*100:.1f}%" for n, _, _ in BANDS) + ".", "", "## Reading", ""]
    gain = held["base"] - held["mae"]
    if gain <= 0:
        L.append(f"- The rating margin model does NOT beat the flat home margin held-out ({gain:+.2f} points): "
                 "price handicaps off the exchange line, not our own number.")
    else:
        L.append(f"- The rating margin model beats the flat home margin by {gain:.2f} points held-out. "
                 "A shadow candidate only; it needs the shadow record before any bar uses it.")
    L += [f"- {len(cache)} settings tried; the held-out line is the honest one.",
          "- No free historical handicap lines, so no return figure: return and CLV come from the shadow record.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = rb.load()
    if len(games) < 1000:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
