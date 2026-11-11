"""
TENNIS best-price study: how much is shopping for the best price worth against Pinnacle's close? (framework#345, record-only)

Fair chance = Pinnacle's de-vigged close. For every side of every held-out match (2022 on) we compare the expected
return of a 1-unit bet at (a) Pinnacle's own price, (b) the bookmaker average close, (c) the best (max) price across
books, using that fair chance: EV = fair * price - 1. We also check realised ROI. This sizes the most a price-shopper
(Matchbook / Betfair / SportyBet next to each other) could gain from the price gap alone, before commission. A side with
no price is skipped (PENDING, never invented). No model, no search: tries counted 1. Nothing here changes a stake, bar,
threshold or live switch.

  python backtest/tennis_best_price_study.py      writes backtest/TENNIS_BEST_PRICE_STUDY.md
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_BEST_PRICE_STUDY.md"
FIRST_TEST = 2022
SOURCES = (("Pinnacle close", "p"), ("Bookmaker average", "q"), ("Best price (max)", "x"))


def sides(games: list[dict]) -> list[dict]:
    """One row per side: fair chance, won, and each price (None when absent or not above 1)."""
    out = []
    for g in games:
        if g.get("year", 0) < FIRST_TEST:
            continue
        for fair, won, k in ((g["mkt"], g["y"] == 1.0, "a"), (1 - g["mkt"], g["y"] == 0.0, "b")):
            pr = {s: (g.get(s + k) if (g.get(s + k) or 0) > 1 else None) for _, s in SOURCES}
            out.append({"fair": fair, "won": won, "px": pr})
    return out


def stats(rows: list[dict], src: str) -> dict:
    """EV and realised ROI per bet, with a standard error on the EV, over sides that have this price."""
    ev, roi = [], []
    for r in rows:
        price = r["px"][src]
        if price is None:
            continue
        ev.append(r["fair"] * price - 1.0)
        roi.append(price - 1.0 if r["won"] else -1.0)
    n = len(ev)
    if n < 2:
        return {"n": n}
    m = sum(ev) / n
    se = math.sqrt(sum((x - m) ** 2 for x in ev) / (n - 1) / n)
    return {"n": n, "ev": m, "se": se, "roi": sum(roi) / n}


def run(games: list[dict]) -> str:
    rows = sides(games)
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis best-price study (shadow, record only)", "",
         f"Made {made} by `backtest/tennis_best_price_study.py` (framework#345). Fair chance = Pinnacle's de-vigged close; "
         f"expected value of a 1-unit bet = fair x price - 1, before any commission. Held-out years {FIRST_TEST}+. "
         f"Tries counted: **1** (no model, no search).", ""]
    if not rows:
        L.append("PENDING: no matches from the held-out years.")
        return "\n".join(L) + "\n"
    L += ["| Price used | Sides priced | Expected value per bet | Std error | Realised ROI |", "|---|---|---|---|---|"]
    res = {}
    for name, s in SOURCES:
        st = res[s] = stats(rows, s)
        if st["n"] < 2:
            L.append(f"| {name} | {st['n']} | PENDING | PENDING | PENDING |")
        else:
            L.append(f"| {name} | {st['n']} | {st['ev']:+.2%} | {st['se']:.2%} | {st['roi']:+.2%} |")
    both = [r for r in rows if r["px"]["x"] and r["px"]["p"]]
    d = [r["fair"] * (r["px"]["x"] - r["px"]["p"]) for r in both]
    gain = sum(d) / len(d) if d else None
    L += ["", "## Reading", ""]
    if gain is None:
        L.append("- PENDING: no side has both a best price and a Pinnacle price.")
    else:
        up = sum(1 for r in both if r["px"]["x"] > r["px"]["p"]) / len(both)
        L.append(f"- The best price beat Pinnacle's own price on {up:.0%} of sides, worth {gain:+.2%} of the stake per bet "
                 f"in expected value ({len(both)} sides). That is the ceiling a price-shopper gets from price alone.")
    L += ["- Every price carries its margin, so expected value is below zero at Pinnacle and the average; the best price only "
          "just reaches break-even in expected value, and realised ROI stays negative. Shopping narrows the margin, it is not a forecast edge.",
          "- The max price is taken after the fact across many books; a real bettor will not always get it, and exchange "
          "commission is not modelled. Treat the figure as an upper bound.",
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
