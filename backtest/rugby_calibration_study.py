"""
RUGBY calibration walk-forward study (framework#344, record-only).

backtest/rugby_backtest.py picks the best Elo (K x home edge). This asks the next question: when that model says 70%,
does the home side win about 70% of the time? Same ESPN games, same replay. Two outputs:
  - a reliability table (held-out years): stated chance bucket vs how often the home side really won;
  - a SHRINK candidate  p' = w * p + (1 - w) * base  (base = home win rate in the tuning years), w tried on
    {0, .25, .5, .75, 1}; every w is counted, chosen on 2014-2019 Brier, reported on 2020+ only.
Record only: nothing here changes a stake, bar, threshold or live switch.

  python backtest/rugby_calibration_study.py      writes backtest/RUGBY_CALIBRATION_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_CALIBRATION_STUDY.md"
WS = (0.0, 0.25, 0.5, 0.75, 1.0)
EDGES = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0001)
MIN_GAMES = 100


def shrink(p: float, base: float, w: float) -> float:
    return w * p + (1 - w) * base


def brier(games, probs, years, base, w) -> dict:
    n, b = 0, 0.0
    for g, p in zip(games, probs):
        if p is None or g["y"] == 0.5 or not (years[0] <= g["year"] <= years[1]):
            continue
        n += 1
        b += (shrink(p, base, w) - g["y"]) ** 2
    return {"n": n, "brier": b / n if n else None}


def reliability(games, probs, years) -> list[dict]:
    rows = []
    for lo, hi in zip(EDGES, EDGES[1:]):
        ps, ys = [], []
        for g, p in zip(games, probs):
            if p is None or g["y"] == 0.5 or not (years[0] <= g["year"] <= years[1]):
                continue
            if lo <= p < hi:
                ps.append(p)
                ys.append(g["y"])
        rows.append({"lo": lo, "hi": min(hi, 1.0), "n": len(ps),
                     "said": sum(ps) / len(ps) if ps else None, "won": sum(ys) / len(ys) if ys else None})
    return rows


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    probs = rb.replay(games, 32.0, 70.0)   # the setting the backtest chose on the tuning years
    tuned = {w: brier(games, probs, rb.TUNE_YEARS, base, w) for w in WS}
    ok = {w: t for w, t in tuned.items() if t["n"] >= MIN_GAMES}
    best = min(ok, key=lambda w: ok[w]["brier"]) if ok else None
    held = brier(games, probs, test, base, best) if best is not None else None
    full = brier(games, probs, test, base, 1.0)
    draws = sum(g["y"] == 0.5 for g in games) / len(games)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby calibration study", "",
         f"Made {made} by `backtest/rugby_calibration_study.py` (framework#344). {len(games)} games, final scores only "
         f"(ESPN). Model: the backtest's tuned Elo (K32, home +70). Shrink weights tried: **{len(WS)}**; chosen on "
         f"{rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**. Draws: {draws:.1%} of games.", "",
         "| Stated home-win chance | Games | Said (mean) | Home side won |", "|---|---|---|---|"]
    for r in reliability(games, probs, test):
        if r["n"]:
            L.append(f"| {r['lo']:.0%}-{r['hi']:.0%} | {r['n']} | {r['said']:.1%} | {r['won']:.1%} |")
        else:
            L.append(f"| {r['lo']:.0%}-{r['hi']:.0%} | 0 | PENDING | PENDING |")
    L += ["", "| Held-out rule | Games | Brier |", "|---|---|---|"]
    if full["n"]:
        L.append(f"| Tuned Elo as is (w=1) | {full['n']} | {full['brier']:.4f} |")
    if held and held["n"]:
        L.append(f"| Shrunk toward home rate, w={best} | {held['n']} | {held['brier']:.4f} |")
    else:
        L.append("| Shrunk | 0 | PENDING |")
    L += ["", "## Reading", ""]
    if held and held["n"] and full["n"]:
        d = full["brier"] - held["brier"]
        L.append(f"- Tuning chose w={best}; held-out Brier {held['brier']:.4f} vs {full['brier']:.4f} unshrunk "
                 + ("(shrinking toward the home rate helps; a shadow candidate)." if d > 0.0005 and best < 1.0 else
                    "(no gain from shrinking)."))
    rel = [r for r in reliability(games, probs, test) if r["n"]]
    if rel:
        n_all = sum(r["n"] for r in rel)
        bias = sum(r["won"] * r["n"] for r in rel) / n_all - sum(r["said"] * r["n"] for r in rel) / n_all
        L.append(f"- Home sides won {bias:+.1%} more than the model said on average ({sum(r['won'] > r['said'] for r in rel)} of "
                 f"{len(rel)} buckets above): " + ("a home-side bias, which shrinking toward the home rate only partly fixes."
                                                 if abs(bias) > 0.02 else "no material bias."))
    L += [f"- {len(WS)} weights tried; the held-out line is the honest one.",
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
