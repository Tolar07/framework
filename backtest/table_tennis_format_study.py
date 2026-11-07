"""
TABLE TENNIS format shadow (framework#342 / #380; record-only).

No free dated WTT/ITTF results feed exists (see VOLLEYBALL_TABLE_TENNIS_STUDY.md), so this is a pure format table, not a
backtest: no result is invented (HR59). It turns a per-point win chance r into a game chance (games go to 11, win by 2),
then into the best-of-5 / best-of-7 match chance, exact game scores and total-games chances. The inverse solves the
per-point chance that reproduces a given match chance (e.g. an exchange or Elo match price), so a shadow board can price
the correct-score and total-games markets from the match price. Whether the independent-points assumption holds is
PENDING until the shadow board has graded table-tennis results (HR35). Nothing here changes a pick, stake or live switch.

  python backtest/table_tennis_format_study.py      writes backtest/TABLE_TENNIS_FORMAT_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "backtest" / "TABLE_TENNIS_FORMAT_STUDY.md"
POINTS = 11


def game_win(r: float, to: int = POINTS) -> float:
    """Chance to win one game to `to` points, win by 2, when each point is won with chance r (independent)."""
    if not 0.0 <= r <= 1.0:
        raise ValueError("r must be in [0, 1]")
    q = 1.0 - r
    p = sum(comb(to - 1 + k, k) * r**to * q**k for k in range(to - 1))          # win to 11 with the loser on 0..9
    tie = comb(2 * (to - 1), to - 1) * (r * q) ** (to - 1)                        # reach 10-10
    deuce = 0.5 if r == q else r * r / (r * r + q * q)                            # then win by 2
    return p + tie * deuce


def score_dist(g: float, best_of: int) -> dict[tuple[int, int], float]:
    """Exact game-score chances (winner games, loser games) from the per-game chance g; keys are (home, away)."""
    need = best_of // 2 + 1
    out: dict[tuple[int, int], float] = {}
    for lost in range(need):
        out[(need, lost)] = comb(need - 1 + lost, lost) * g**need * (1 - g) ** lost
        out[(lost, need)] = comb(need - 1 + lost, lost) * (1 - g) ** need * g**lost
    return out


def match_win(g: float, best_of: int) -> float:
    need = best_of // 2 + 1
    return sum(p for (h, _a), p in score_dist(g, best_of).items() if h == need)


def total_games_over(g: float, best_of: int, line: float) -> float:
    return sum(p for (h, a), p in score_dist(g, best_of).items() if h + a > line)


def solve_point_chance(match_p: float, best_of: int) -> float | None:
    """Per-point chance r whose best-of-N match chance equals match_p (bisection; monotone). None if out of (0, 1)."""
    if not 0.0 < match_p < 1.0:
        return None
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if match_win(game_win(mid), best_of) < match_p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def price(match_p: float, best_of: int = 5) -> dict | None:
    """Correct-score and total-games chances implied by a match-win chance (the shadow-board hook)."""
    r = solve_point_chance(match_p, best_of)
    if r is None:
        return None
    g = game_win(r)
    need = best_of // 2 + 1
    lines = [need + 0.5 + i for i in range(best_of - need)]
    return {"point": r, "game": g, "scores": score_dist(g, best_of),
            "over": {ln: total_games_over(g, best_of, ln) for ln in lines}}


def run() -> str:
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Table tennis format shadow", "",
         f"Made {made} by `backtest/table_tennis_format_study.py` (framework#342, #380). Record only.", "",
         "A pure format table (no results data exists to backtest on, HR35/HR59): per-point chance -> game (to 11, win by 2) "
         "-> best-of-5 / best-of-7 match. Assumes points are independent; that is PENDING a grade on the shadow board.", "",
         "## Point chance -> game and match chance", "",
         "| Point chance | Game chance | Best-of-5 match | Best-of-7 match |", "|---|---|---|---|"]
    for r in (0.50, 0.52, 0.54, 0.56, 0.58, 0.60, 0.65):
        g = game_win(r)
        L.append(f"| {r:.0%} | {g:.1%} | {match_win(g, 5):.1%} | {match_win(g, 7):.1%} |")
    L += ["", "## Best-of-5 prices implied by a match chance", "",
          "| Match chance | Point chance | 3-0 | 3-1 | 3-2 | Over 3.5 games | Over 4.5 games |", "|---|---|---|---|---|---|---|"]
    for m in (0.50, 0.60, 0.70, 0.80, 0.90):
        p = price(m, 5)
        s = p["scores"]
        L.append(f"| {m:.0%} | {p['point']:.1%} | {s[(3, 0)]:.1%} | {s[(3, 1)]:.1%} | {s[(3, 2)]:.1%} | "
                 f"{p['over'][3.5]:.1%} | {p['over'][4.5]:.1%} |")
    L += ["", "(3-0 / 3-1 / 3-2 are the favourite's wins; the underdog's mirror scores are in `price()`.)", "",
          "## Reading", "",
          "- A small point edge compounds: 54% of points is a 65% game and a 77% best-of-5 match.",
          "- The favourite wins in straight games more often as the match chance rises; the shadow board grades the "
          "independent-points assumption against real results before any of this is trusted (the volleyball momentum study "
          "found independence under-predicted straight sets there).",
          "- Method sources (YouTube, transcript-only): https://www.youtube.com/watch?v=zUUXMhxZgZY @ 02:12 (own Elo), "
          "@ 02:44 (fatigue / travel since last tournament, motivation by tournament level), @ 03:50 (stage-of-tournament "
          "patterns): candidate record-only inputs once a results feed exists. https://www.youtube.com/watch?v=Hv1DQtxPraU "
          "@ 02:44 (mined patterns revert to the mean) and @ 07:02 (fit a distribution, then project).",
          "- Record only: nothing here changes a stake, a bar or the live switch. Setka Cup and similar leagues stay excluded."]
    return "\n".join(L) + "\n"


def main() -> None:
    OUT.write_text(run(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
