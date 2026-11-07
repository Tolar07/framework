"""
VOLLEYBALL set-momentum shadow (framework#342 / #380; record-only).

The set-score shadow (volleyball_sets_study.py) assumed sets are independent and under-predicted straight-sets wins
(model 31% vs actual 48.7%). This adds ONE parameter m: the chance the home side wins a set moves by +m after it won
the previous set and -m after it lost it (a momentum / persistence term). For each match the first-set chance q is
solved so the best-of-5 MATCH chance still equals the Elo chance. m is picked on the tuning years (5 settings tried,
all counted) and reported on the held-out years only. Missing data reads PENDING (HR35). Nothing here changes a pick,
stake or the live switch.

  python backtest/volleyball_momentum_study.py      writes backtest/VOLLEYBALL_MOMENTUM_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import volleyball_backtest as vb  # noqa: E402
from backtest import volleyball_sets_study as ss  # noqa: E402

OUT = ROOT / "backtest" / "VOLLEYBALL_MOMENTUM_STUDY.md"
MOMENTA = (0.0, 0.05, 0.10, 0.15, 0.20)
EPS = 1e-6


def score_probs(q: float, m: float) -> dict[str, float]:
    """Best-of-5 correct-score chances; set-1 chance q, then q+m after a home set win, q-m after a loss."""
    @lru_cache(maxsize=None)
    def walk(h: int, a: int, last: int) -> tuple:
        if h == 3 or a == 3:
            return ((f"{h}-{a}", 1.0),)
        p = min(max(q + m * last, 0.001), 0.999)
        out: dict[str, float] = {}
        for k, w in walk(h + 1, a, 1):
            out[k] = out.get(k, 0.0) + p * w
        for k, w in walk(h, a + 1, -1):
            out[k] = out.get(k, 0.0) + (1 - p) * w
        return tuple(out.items())
    d = dict(walk(0, 0, 0))
    return {k: d.get(k, 0.0) for k in ss.SCORES}


def match_win(q: float, m: float) -> float:
    s = score_probs(q, m)
    return s["3-0"] + s["3-1"] + s["3-2"]


def solve_q(p: float, m: float) -> float:
    """Set-1 chance whose best-of-5 match chance is p (rises with q, so bisect)."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if match_win(mid, m) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def evaluate(games, probs, years, flat, m) -> dict:
    n = 0
    ll = ll0 = sweep_pred = sweep_act = 0.0
    for g, p in zip(games, probs):
        if p is None or not (years[0] <= g["year"] <= years[1]):
            continue
        key = f"{int(g['hs'])}-{int(g['as'])}"
        if key not in ss.SCORES:
            continue
        s = score_probs(solve_q(min(max(p, EPS), 1 - EPS), m), m)
        n += 1
        ll += -math.log(max(s[key], EPS))
        ll0 += -math.log(max(flat[key], EPS))
        sweep_pred += s["3-0"] + s["0-3"]
        sweep_act += key in ("3-0", "0-3")
    if not n:
        return {"n": 0}
    return {"n": n, "ll": ll / n, "ll0": ll0 / n, "sweep_pred": sweep_pred / n, "sweep_act": sweep_act / n}


def run(games: list[dict]) -> str:
    last = max((g["year"] for g in games), default=vb.TUNE_YEARS[1])
    test = (vb.TUNE_YEARS[1] + 1, last)
    tune = [g for g in games if vb.TUNE_YEARS[0] <= g["year"] <= vb.TUNE_YEARS[1]]
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Volleyball set-momentum shadow", "",
         f"Made {made} by `backtest/volleyball_momentum_study.py` (framework#342, #380). Record only."]
    if len(tune) < vb.MIN_TUNE_N:
        return "\n".join(L + ["", "- PENDING: too little tuning data."]) + "\n"
    flat = {k: (sum(f"{int(g['hs'])}-{int(g['as'])}" == k for g in tune) + 1) / (len(tune) + len(ss.SCORES))
            for k in ss.SCORES}
    probs = rb.replay(games, 24.0, 0.0)
    tuned = {m: evaluate(games, probs, vb.TUNE_YEARS, flat, m) for m in MOMENTA}
    if not all(r["n"] for r in tuned.values()):
        return "\n".join(L + ["", "- PENDING: no tuning matches rated."]) + "\n"
    best = min(MOMENTA, key=lambda m: tuned[m]["ll"])
    held = {m: evaluate(games, probs, test, flat, m) for m in (0.0, best)}
    if not held[best]["n"]:
        return "\n".join(L + ["", "- PENDING: no held-out matches rated."]) + "\n"
    ind, mom = held[0.0], held[best]
    gain = ind["ll"] - mom["ll"]
    L += ["", f"Candidate: set-1 chance solved from the Elo match chance (K24, no home edge), then +/-m by who won the "
              f"previous set. **{len(MOMENTA)} settings tried** (m = {', '.join(str(m) for m in MOMENTA)}); chosen on "
              f"{vb.TUNE_YEARS[0]}-{vb.TUNE_YEARS[1]} (best m = {best}); reported on **{test[0]}-{test[1]} only** "
              f"({mom['n']} matches).", "",
          f"| Rule (held-out years) | Log loss of the actual score | Straight-sets share (actual {mom['sweep_act']:.1%}) |",
          "|---|---|---|",
          f"| Independent sets (m=0) | {ind['ll']:.4f} | {ind['sweep_pred']:.1%} |",
          f"| Momentum m={best} | {mom['ll']:.4f} | {mom['sweep_pred']:.1%} |",
          f"| Flat historical shares | {mom['ll0']:.4f} | n/a |", "",
          "## Reading", "",
          f"- Momentum vs independent sets: {gain:+.4f} log loss "
          + ("(momentum helps: a shadow candidate for correct-score / set markets)." if gain > 0.002
             else "(no real help: keep independent sets)."),
          f"- Straight-sets gap (model vs actual) went from {abs(ind['sweep_pred'] - ind['sweep_act']):.1%} to "
          f"{abs(mom['sweep_pred'] - mom['sweep_act']):.1%}.",
          "- College data, not the pro leagues in scope. No free closing odds, so this is accuracy, not return.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = vb.load()
    if len(games) < 2000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
