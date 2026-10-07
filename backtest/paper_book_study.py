"""
PAPER BOOK STUDY — how the system's own paper bets are doing (Architect
2026-10-07: "place bets within yourself and see how the outcome is").

Reads every graded game (data/universe/, engine/universe.py), places the
paper bets of engine/paper_book.STRATEGIES at the first price seen, settles
them and writes backtest/PAPER_BOOK.md: per rule the bets, win rate, return
per £1 with its standard error, average CLV, a £100 paper bankroll at £1 a
bet, the split covered / not covered by the board, and a verdict. A rule
marked READY TO PROPOSE is put to the Architect; nothing here stakes money.

    python backtest/paper_book_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import paper_book as pb  # noqa: E402
from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "PAPER_BOOK.md"


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x:+.1%}"


def main() -> int:
    rows = [r for r in uv.load_graded() if r.get("result")]
    sc = pb.score(rows)
    L = ["# PAPER BOOK — the system's own £1 paper bets on every game it watches", "",
         "Written by `backtest/paper_book_study.py`. Each rule (`engine/paper_book.py`) was fixed before any "
         "result was seen and bets £1 at the FIRST price the sweep saw; CLV = that price against the last "
         "pre-kick-off price (positive = the market moved towards the bet). A rule is READY TO PROPOSE only "
         f"with {pb.MIN_BETS}+ bets, a return {pb.SE_BAR:g} standard errors above zero and a positive CLV — "
         "then it goes to the Architect. Paper only: nothing here stakes money.", "",
         f"{len(rows)} graded games so far.", "",
         "| Rule | what it bets | bets | won | £1 return ± 1 se | avg CLV | £100 bankroll | covered / not covered return | verdict |",
         "|---|---|---|---|---|---|---|---|---|"]
    for name, (_sport, desc, _fn) in pb.STRATEGIES.items():
        s = sc[name]
        a, c, u = s["all"], s["covered"], s["not covered"]
        if a.n == 0:
            L.append(f"| {name} | {desc} | 0 | — | — | — | £100.00 | — | learning (0/{pb.MIN_BETS} bets) |")
            continue
        L.append(f"| {name} | {desc} | {a.n} | {a.won / a.n:.0%} | {a.roi():+.1%} ± {a.se():.1%} | "
                 f"{_pct(a.avg_clv())} | £{100 + a.pnl:.2f} | {_pct(c.roi() if c.n else None)} / "
                 f"{_pct(u.roi() if u.n else None)} | {a.verdict()} |")
    ready = [n for n in pb.STRATEGIES if sc[n]["all"].verdict() == "READY TO PROPOSE"]
    L += ["", "**Ready to propose:** " + (", ".join(ready) if ready else "none yet — the book needs more graded games."),
          "", "A rule's return is only trusted once it is large against its standard error: with £1 bets at "
          "~1.9, one standard error is about 95% ÷ √bets (≈ 9.5% at 100 bets, 3% at 1,000).", ""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
