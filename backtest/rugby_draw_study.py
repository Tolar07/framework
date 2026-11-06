"""
RUGBY draw-chance walk-forward study (framework#344, record-only SHADOW candidate).

The board's 1X2 (SportyBet market 1, 80 minutes) has a draw side, but the Elo counts a draw as half a win and has no
draw price. Idea (standard in 3-way sports models): the draw chance is highest between evenly matched sides. Here:
three-way chances P(home)=e-d/2, P(draw)=d, P(away)=1-e-d/2, where e is the per-league-home-edge Elo chance
(backtest/rugby_inputs_study.py) and d is either one flat draw rate or a rate per |e-0.5| bucket. The draw rates
are learned from the tuning years only (2014-2019), reported on 2020+ only, every variant counted.

Record only: nothing here changes a stake, bar, threshold or the live switch.

  python backtest/rugby_draw_study.py      writes backtest/RUGBY_DRAW_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402
from backtest import rugby_inputs_study as ri  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_DRAW_STUDY.md"
EDGES = (0.10, 0.25)              # bucket edges on |e - 0.5|: close / medium / lopsided
MIN_BUCKET = 30
EPS = 1e-6


def bucket(e: float) -> int:
    gap = abs(e - 0.5)
    return sum(gap >= x for x in EDGES)


def draw_rates(games, probs, years) -> tuple[float, list[float]]:
    """(flat draw rate, per-bucket draw rate) over rated games in years. A thin bucket falls back to the flat rate."""
    n = dr = 0
    bn, bd = [0] * (len(EDGES) + 1), [0] * (len(EDGES) + 1)
    for g, p in zip(games, probs, strict=True):
        if p is None or not (years[0] <= g["year"] <= years[1]):
            continue
        d = g["y"] == 0.5
        n += 1
        dr += d
        b = bucket(p)
        bn[b] += 1
        bd[b] += d
    flat = dr / n if n else 0.0
    return flat, [bd[i] / bn[i] if bn[i] >= MIN_BUCKET else flat for i in range(len(bn))]


def three_way(e: float, d: float) -> tuple[float, float, float]:
    d = min(max(d, 0.0), 2 * min(e, 1 - e))   # never more draw than the smaller side can give up
    return e - d / 2, d, 1 - e - d / 2


def score(games, probs, years, rule) -> dict:
    """rule(e) -> draw chance. Multiclass Brier (sum of 3 squared errors) and log loss over rated games."""
    n = 0
    br = ll = 0.0
    for g, e in zip(games, probs, strict=True):
        if e is None or not (years[0] <= g["year"] <= years[1]):
            continue
        ph, pd_, pa = three_way(e, rule(e))
        out = (1, 0, 0) if g["y"] == 1.0 else (0, 1, 0) if g["y"] == 0.5 else (0, 0, 1)
        br += (ph - out[0]) ** 2 + (pd_ - out[1]) ** 2 + (pa - out[2]) ** 2
        ll -= math.log(max((ph, pd_, pa)[out.index(1)], EPS))
        n += 1
    return {"n": n, "brier": br / n if n else None, "logloss": ll / n if n else None}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    home, tries = ri.best_home_by_league(games, False)
    probs = ri.replay(games, home, False)
    flat, rates = draw_rates(games, probs, rb.TUNE_YEARS)
    tries += 2   # flat rate, bucketed rates
    none = score(games, probs, test, lambda e: 0.0)
    fl = score(games, probs, test, lambda e: flat)
    bk = score(games, probs, test, lambda e: rates[bucket(e)])
    held_draws = sum(1 for g, p in zip(games, probs, strict=True)
                     if p is not None and test[0] <= g["year"] <= test[1] and g["y"] == 0.5)
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby draw-chance study (3-way 1X2)", "",
         f"Made {made} by `backtest/rugby_draw_study.py` (framework#344). {len(games)} games, final scores only "
         f"(ESPN). Variants tried: **{tries}**; draw rates learned on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, "
         f"reported on **{test[0]}-{test[1]} only** ({held_draws} drawn games).", "",
         "| Draw rule (held-out years) | Games | 3-way Brier | Log loss |", "|---|---|---|---|"]
    for nm, r in (("No draw chance (Elo as is)", none), (f"Flat draw rate {flat:.1%}", fl),
                  ("Draw rate by Elo gap " + " / ".join(f"{x:.1%}" for x in rates), bk)):
        L.append(f"| {nm} | {r['n']} | {r['brier']:.4f} | {r['logloss']:.4f} |" if r["n"]
                 else f"| {nm} | 0 | PENDING | PENDING |")
    L += ["", "## Reading", ""]
    if fl["n"] and bk["n"]:
        gain = fl["logloss"] - bk["logloss"]
        L.append(f"- Gap-based draw rate changed held-out log loss by {gain:+.4f} vs a flat rate "
                 + ("(a shadow candidate for the draw side, to be confirmed on the shadow board's record)."
                    if gain > 0.0005 else "(no real help: a flat draw rate is enough)."))
        L.append(f"- A flat draw rate changed log loss by {none['logloss'] - fl['logloss']:+.4f} vs no draw chance.")
    else:
        L.append("- PENDING: too little data.")
    L += [f"- {tries} variants tried; the held-out line is the honest one.",
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
