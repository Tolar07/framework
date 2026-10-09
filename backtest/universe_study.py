"""
UNIVERSE STUDY — what SportyBet's prices get right and wrong, on every
football and basketball game it lists, covered by the board or not
(Architect 2026-10-07: learn "how the betting goes on them").

Reads data/universe/graded_*.jsonl (engine/universe.py) and writes
backtest/UNIVERSE_STUDY.md:
  1. every market side: how often it landed vs the chance SportyBet's last
     price implied (margin removed), and the return of backing it at £1;
  2. the same by price band — where the bookmaker's favourite / long-shot
     pricing leans;
  3. competitions where a side returned clearly more or less than the margin
     costs (two standard errors from zero, 30+ games) — candidates to study,
     not picks;
  4. covered vs not-covered games;
  5. price moves: a side whose price shortened before kick-off — did it land
     more often than its FIRST price said (the market learning late news)?
Nothing here selects a pick. A finding becomes a rule only by the Architect.

    python backtest/universe_study.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "UNIVERSE_STUDY.md"
MIN_N = 30
BANDS = ((1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 1000.0))


def _fair(price: float, market: list[float]) -> float:
    return (1 / price) / sum(1 / p for p in market)


class Acc:
    def __init__(self):
        self.n = self.won = 0
        self.fair = self.ret = self.ret2 = 0.0

    def add(self, won: int, price: float, fair: float) -> None:
        r = won * price - 1
        self.n += 1
        self.won += won
        self.fair += fair
        self.ret += r
        self.ret2 += r * r

    def roi(self) -> float:
        return self.ret / self.n if self.n else 0.0

    def se(self) -> float:
        if self.n < 2:
            return float("inf")
        m = self.ret / self.n
        return sqrt(max(self.ret2 / self.n - m * m, 0.0) / (self.n - 1))

    def row(self, name: str) -> str:
        return (f"| {name} | {self.n} | {self.won / self.n:.1%} | {self.fair / self.n:.1%} | "
                f"{(self.won - self.fair) / self.n:+.1%} | {self.roi():+.1%} ± {self.se():.1%} |")


HEAD = ("| Side | bets | landed | fair chance (last price) | landed − fair | £1 return ± 1 se |",
        "|---|---|---|---|---|---|")


def main() -> int:
    rows = [r for r in uv.load_graded() if r.get("result")]
    every = uv.load_graded()
    L = ["# UNIVERSE STUDY — SportyBet's prices on every game, covered or not", "",
         "Written by `backtest/universe_study.py` from `data/universe/graded_*.jsonl` "
         "(`monitor/universe_sweep.py`, every 3 hours). Fair chance = the last pre-kick-off price "
         "with SportyBet's margin removed. A study, not a selector.", ""]
    if not rows:
        L.append("No graded game yet — NO DATA — PENDING (the first sweep archives games once they have "
                 "been played and their result is found).")
        OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
        print("\n".join(L))
        return 0
    found = len(rows) / len(every)
    L += [f"{len(rows)} games graded ({found:.0%} of {len(every)} looked up; the rest had no unambiguous "
          f"result on Flashscore), kick-offs {min(r['ko'] for r in rows)[:10]} to {max(r['ko'] for r in rows)[:10]}.", ""]
    for sport in ("football", "basketball"):
        srows = [r for r in rows if r["sport"] == sport]
        L.append(f"## {sport.capitalize()} — {len(srows)} games")
        L.append("")
        if not srows:
            L += ["NO DATA — PENDING.", ""]
            continue
        side: dict[str, Acc] = defaultdict(Acc)
        band: dict[str, Acc] = defaultdict(Acc)
        comp: dict[tuple[str, str], Acc] = defaultdict(Acc)
        cov: dict[tuple[bool, str], Acc] = defaultdict(Acc)
        moved: dict[str, Acc] = defaultdict(Acc)
        for r in srows:
            first = {k: (won, price) for k, won, price, _m in uv.outcomes(sport, r["first"]["p"], r["result"])}
            for k, won, price, mkt in uv.outcomes(sport, r["last"]["p"], r["result"]):
                if k[1:3] == "up":
                    continue       # early payout: outcomes overlap, no fair chance — measured by paper rules F11-F13
                f = _fair(price, mkt)
                side[k].add(won, price, f)
                lo, hi = next(b for b in BANDS if b[0] <= price < b[1])
                band[f"{k.split(':')[0]} @ {lo:.2f}–{hi:.2f}"].add(won, price, f)
                comp[(f"{r['country']} · {r['comp']}", k)].add(won, price, f)
                cov[(r["covered"], k.split(":")[0])].add(won, price, f)
                if k in first and r["looks"] > 1:
                    p0 = first[k][1]
                    tag = ("shortened 3%+" if price < p0 * 0.97 else
                           "drifted 3%+" if price > p0 * 1.03 else "steady")
                    moved[tag].add(won, p0, _fair(price, mkt))        # return at the FIRST price
        L += ["### Every market side", "", *HEAD]
        L += [side[k].row(k) for k in sorted(side)]
        L += ["", "### By price band (all sides of a market together)", "", *HEAD]
        L += [band[k].row(k) for k in sorted(band, key=lambda k: (k.split(" @ ")[0], float(k.split(" @ ")[1].split("–")[0])))
              if band[k].n >= MIN_N]
        stand = [(k, a) for k, a in comp.items() if a.n >= MIN_N and abs(a.roi()) > 2 * a.se()]
        stand.sort(key=lambda x: -x[1].roi())
        L += ["", f"### Competitions where a side stood out ({MIN_N}+ games, return two se or more from zero)", ""]
        if stand:
            L += [*HEAD]
            L += [a.row(f"{c} — {k}") for (c, k), a in stand[:20]]
        else:
            L.append(f"None yet — a competition needs {MIN_N}+ graded games of a side, and a return two "
                     "standard errors from zero, to be listed.")
        L += ["", "### Covered by the board vs not", "", "| | market | bets (every side) | landed − fair | £1 return |", "|---|---|---|---|---|"]
        for (c, m), a in sorted(cov.items(), key=lambda x: (x[0][1], not x[0][0])):
            L.append(f"| {'covered' if c else 'not covered'} | {m} | {a.n} | {(a.won - a.fair) / a.n:+.1%} | {a.roi():+.1%} |")
        L += ["", "### Price moves before kick-off (return at the FIRST price seen)", "",
              "A side that shortened 3%+ between the first and last look — did backing it early pay?", "", *HEAD]
        L += [moved[k].row(k) for k in ("shortened 3%+", "steady", "drifted 3%+") if moved[k].n]
        L.append("")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
