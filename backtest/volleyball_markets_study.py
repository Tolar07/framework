"""
VOLLEYBALL set-market shadow (framework#342; record-only).

Prices the volleyball set markets (total sets over 3.5 / over 4.5, home -1.5 sets, away -1.5 sets) from the set-momentum
score model (backtest/volleyball_momentum_study.py, Elo K24 match chance -> set-1 chance -> +/-m by the last set) and
scores each walk-forward on the held-out years by Brier against the flat tuning-year frequency of the same market.
m is picked on the tuning years (5 settings tried, all counted). Cached ESPN NCAA women's results, college not pro.
Missing data reads PENDING (HR35). Nothing here changes a pick, stake or the live switch.

  python backtest/volleyball_markets_study.py      writes backtest/VOLLEYBALL_MARKETS_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import volleyball_backtest as vb  # noqa: E402
from backtest import volleyball_momentum_study as ms  # noqa: E402

OUT = ROOT / "backtest" / "VOLLEYBALL_MARKETS_STUDY.md"
EPS = 1e-6
MARKETS = {  # name -> correct scores (home-away sets) on which the yes side wins
    "Over 3.5 sets": ("3-1", "1-3", "3-2", "2-3"),
    "Over 4.5 sets (five sets)": ("3-2", "2-3"),
    "Home -1.5 sets": ("3-0", "3-1"),
    "Away -1.5 sets": ("0-3", "1-3"),
}


def market_probs(p: float, m: float) -> dict[str, float]:
    s = ms.score_probs(ms.solve_q(min(max(p, EPS), 1 - EPS), m), m)
    return {k: sum(s[x] for x in v) for k, v in MARKETS.items()}


def evaluate(games, probs, years, flat, m) -> dict:
    n = 0
    br = {k: 0.0 for k in MARKETS}
    b0 = {k: 0.0 for k in MARKETS}
    for g, p in zip(games, probs):
        if p is None or not (years[0] <= g["year"] <= years[1]):
            continue
        key = f"{int(g['hs'])}-{int(g['as'])}"
        mp = market_probs(p, m)
        n += 1
        for k, v in MARKETS.items():
            y = float(key in v)
            br[k] += (mp[k] - y) ** 2
            b0[k] += (flat[k] - y) ** 2
    if not n:
        return {"n": 0}
    return {"n": n, "br": {k: x / n for k, x in br.items()}, "b0": {k: x / n for k, x in b0.items()}}


def run(games: list[dict]) -> str:
    last = max((g["year"] for g in games), default=vb.TUNE_YEARS[1])
    test = (vb.TUNE_YEARS[1] + 1, last)
    tune = [g for g in games if vb.TUNE_YEARS[0] <= g["year"] <= vb.TUNE_YEARS[1]]
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Volleyball set-market shadow", "",
         f"Made {made} by `backtest/volleyball_markets_study.py` (framework#342). Record only."]
    if len(tune) < vb.MIN_TUNE_N:
        return "\n".join(L + ["", "- PENDING: too little tuning data."]) + "\n"
    flat = {k: sum(f"{int(g['hs'])}-{int(g['as'])}" in v for g in tune) / len(tune) for k, v in MARKETS.items()}
    probs = rb.replay(games, 24.0, 0.0)
    tuned = {m: evaluate(games, probs, vb.TUNE_YEARS, flat, m) for m in ms.MOMENTA}
    if not all(r["n"] for r in tuned.values()):
        return "\n".join(L + ["", "- PENDING: no tuning matches rated."]) + "\n"
    best = min(ms.MOMENTA, key=lambda m: sum(tuned[m]["br"].values()))
    held = evaluate(games, probs, test, flat, best)
    if not held["n"]:
        return "\n".join(L + ["", "- PENDING: no held-out matches rated."]) + "\n"
    L += ["", f"Candidate: momentum score model (Elo K24, no home edge). **{len(ms.MOMENTA)} settings tried** "
              f"(m = {', '.join(str(m) for m in ms.MOMENTA)}); chosen on {vb.TUNE_YEARS[0]}-{vb.TUNE_YEARS[1]} "
              f"(best m = {best}); reported on **{test[0]}-{test[1]} only** ({held['n']} matches).", "",
          "| Market (held-out years) | Model Brier | Flat-rate Brier | Model better by |", "|---|---|---|---|"]
    wins = 0
    for k in MARKETS:
        d = held["b0"][k] - held["br"][k]
        wins += d > 0.0005
        L.append(f"| {k} | {held['br'][k]:.4f} | {held['b0'][k]:.4f} | {d:+.4f} |")
    L += ["", "## Reading", "",
          f"- Model beats the flat rate on {wins} of {len(MARKETS)} markets "
          + ("(a shadow candidate for the set markets, to be confirmed on the shadow board)." if wins >= 3
             else "(too few: leave the set markets on the exchange price)."),
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
