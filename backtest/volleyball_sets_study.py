"""
VOLLEYBALL set-score shadow (framework#342 / #380; record-only).

Turns the Elo match-win chance into a best-of-5 correct-score distribution (3-0, 3-1, 3-2 either way) by solving for the
per-set chance q whose best-of-5 match chance equals the Elo chance, then scores it walk-forward on the held-out years
against the flat historical score shares from the tuning years. Uses the cached ESPN NCAA women's results of
backtest/volleyball_backtest.py. Missing data reads PENDING (HR35). Nothing here changes a pick, stake or the live switch.

  python backtest/volleyball_sets_study.py      writes backtest/VOLLEYBALL_SETS_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import volleyball_backtest as vb  # noqa: E402

OUT = ROOT / "backtest" / "VOLLEYBALL_SETS_STUDY.md"
SCORES = ("3-0", "3-1", "3-2", "2-3", "1-3", "0-3")   # home sets - away sets
EPS = 1e-6


def score_probs(q: float) -> dict[str, float]:
    """Best-of-5 correct-score chances when the home side wins each set with chance q (sets independent)."""
    p, r = q, 1 - q
    c = math.comb
    return {"3-0": p**3, "3-1": c(3, 1) * p**3 * r, "3-2": c(4, 2) * p**3 * r**2,
            "2-3": c(4, 2) * r**3 * p**2, "1-3": c(3, 1) * r**3 * p, "0-3": r**3}


def match_win(q: float) -> float:
    s = score_probs(q)
    return s["3-0"] + s["3-1"] + s["3-2"]


def solve_q(m: float) -> float:
    """Per-set chance whose best-of-5 match chance is m (match_win rises with q, so bisect)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if match_win(mid) < m:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def evaluate(games, probs, years, flat) -> dict:
    n = 0
    ll = ll0 = sweep_pred = sweep_act = 0.0
    for g, m in zip(games, probs):
        if m is None or not (years[0] <= g["year"] <= years[1]):
            continue
        key = f"{int(g['hs'])}-{int(g['as'])}"
        if key not in SCORES:
            continue
        s = score_probs(solve_q(min(max(m, EPS), 1 - EPS)))
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
    L = ["# Volleyball set-score shadow", "",
         f"Made {made} by `backtest/volleyball_sets_study.py` (framework#342, #380). Record only."]
    if len(tune) < vb.MIN_TUNE_N:
        return "\n".join(L + ["", "- PENDING: too little tuning data."]) + "\n"
    flat = {k: (sum(f"{int(g['hs'])}-{int(g['as'])}" == k for g in tune) + 1) / (len(tune) + len(SCORES)) for k in SCORES}
    probs = rb.replay(games, 24.0, 0.0)   # the shared board setting; no tuning here, one candidate only
    r = evaluate(games, probs, test, flat)
    if not r["n"]:
        return "\n".join(L + ["", "- PENDING: no held-out matches rated."]) + "\n"
    gain = r["ll0"] - r["ll"]
    L += ["", f"Candidate: per-set chance solved from the Elo match chance (K24, no home edge), sets independent. "
              f"**1 setting tried.** Flat shares fitted on {vb.TUNE_YEARS[0]}-{vb.TUNE_YEARS[1]}; reported on "
              f"**{test[0]}-{test[1]} only** ({r['n']} matches).", "",
          "| Rule | Log loss of the actual score (lower is better) |", "|---|---|",
          f"| Elo -> best-of-5 score model | {r['ll']:.4f} |", f"| Flat historical score shares | {r['ll0']:.4f} |", "",
          "## Reading", "",
          f"- Score model vs flat shares: {gain:+.4f} log loss "
          + ("(the Elo-driven score model beats the flat shares: a shadow candidate for correct-score / set markets)."
             if gain > 0.002 else "(no real help: leave correct-score markets without a model edge)."),
          f"- Straight-sets share: model {r['sweep_pred']:.1%} vs actual {r['sweep_act']:.1%} "
          + ("(close: sets-independence holds well enough)." if abs(r["sweep_pred"] - r["sweep_act"]) < 0.03
             else "(gap: sets are not independent; a momentum/set-correlation term is the next study)."),
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
