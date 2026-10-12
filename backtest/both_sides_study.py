"""
BOTH SIDES STUDY — does learning from every graded game, bet on or not,
make the picks better? (Architect 2026-10-12: "every market is yes or no ...
learn from it, don't block it ... I want to see that there's an improvement.")

Every side of every market SportyBet priced on every graded football and basketball game
(data/universe/, engine/universe.py: 1X2, double chance, BTTS yes/no,
Over/Under 0.5-4.5, 1UP/2UP) is one 1/0 record: the chance SportyBet's price
gave it (margin removed) and whether it landed. Records are grouped by
outcome x price band ("BTTS no at 1.50-2.00").

WALK-FORWARD, one day at a time: a group's correction is learned ONLY from
the days before the day being tested — the same shrunk, capped, evidence-gated
shift engine/learning.py uses (50+ results, 2 standard errors, cap 10 pts).
Then on the test day:
  * Brier score of the plain chances vs the corrected chances (lower = better);
  * one £1 pick per game, the way the board picks (price 1.20-2.00, chance 50%+):
      A  likeliest outcome on the plain chances;
      B  likeliest outcome on the learned chances;
      C  learned chances, best value (chance x price) within 2 pts of the top.

    python backtest/both_sides_study.py      -> backtest/BOTH_SIDES_STUDY.md
"""
from __future__ import annotations

import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "BOTH_SIDES_STUDY.md"
BANDS = (1.0, 1.20, 1.40, 1.60, 2.00, 3.00, 1e9)
MIN_N, Z_MIN, SHRINK, MAX_SHIFT = 50, 2.0, 30, 0.10
LO, HI, FLOOR, EV_WINDOW = 1.20, 2.00, 0.50, 0.02


def band(price: float) -> str:
    for lo, hi in zip(BANDS, BANDS[1:]):
        if lo <= price < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi < 1e8 else f"{lo:.2f}+"
    return "?"


def label(sport: str, rec: dict) -> str:
    """A group name that is the same from game to game: team names and basketball
    lines are dropped, the side and the line in goals are kept."""
    k = rec["key"]
    if sport == "football":
        from engine import full_markets as fm
        return fm.display_key(k)
    market, side = k.split("|")[0], k.split("|")[-1]
    if market == "hcp":
        line = rec.get("line", 0.0)
        gets = line if side == "home" else -line          # points this side is given
        return f"handicap {'underdog' if gets > 0 else 'favourite'}"
    return f"{'total' if market == 'total' else 'winner'} {side}"


def records(row: dict) -> list[dict]:
    """Every settled side of every market of one graded game, with a fair chance."""
    out = []
    for r in uv.all_records(row):
        if r["fair"] is None or r["price"] <= 1:
            continue
        out.append({**r, "seg": f"{label(row['sport'], r)} @{band(r['price'])}"})
    return out


def learn(history: list[dict]) -> dict[str, float]:
    """seg -> chance shift, from earlier days only."""
    acc: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for r in history:
        a = acc[r["seg"]]
        a[0] += 1
        a[1] += r["won"]
        a[2] += r["fair"]
        a[3] += r["fair"] * (1 - r["fair"])
    out = {}
    for seg, (n, w, e, v) in acc.items():
        z = (w - e) / sqrt(v) if v > 0 else 0.0
        if n >= MIN_N and abs(z) >= Z_MIN:
            out[seg] = max(-MAX_SHIFT, min(MAX_SHIFT, (w - e) / (n + SHRINK)))
    return out


def pick(recs: list[dict], chance, value: bool) -> dict | None:
    pool = [r for r in recs if LO <= r["price"] <= HI and chance(r) >= FLOOR]
    if not pool:
        return None
    top = max(chance(r) for r in pool)
    if not value:
        return max(pool, key=chance)
    return max((r for r in pool if chance(r) >= top - EV_WINDOW), key=lambda r: chance(r) * r["price"])


class Book:
    def __init__(self) -> None:
        self.n = self.won = 0
        self.pnl = self.pnl2 = self.exp = 0.0

    def add(self, r: dict, c: float) -> None:
        p = r["won"] * r["price"] - 1
        self.n += 1
        self.won += r["won"]
        self.pnl += p
        self.pnl2 += p * p
        self.exp += c

    def line(self) -> str:
        if not self.n:
            return "— | — | — | —"
        m = self.pnl / self.n
        se = sqrt(max(self.pnl2 / self.n - m * m, 0) / max(self.n - 1, 1))
        return f"{self.n} | {self.won} ({self.won / self.n:.1%}) | {self.exp:.0f} | {m:+.1%} ± {se:.1%}"


def run(sport: str, games: list[dict]) -> list[str]:
    by_day: dict[str, list[list[dict]]] = defaultdict(list)
    for g in games:
        recs = records(g)
        if recs:
            by_day[(g.get("ko") or "")[:10]].append(recs)
    days = sorted(d for d in by_day if d)
    history: list[dict] = []
    brier_plain = brier_learned = 0.0
    n_brier = 0
    books = {"A": Book(), "B": Book(), "C": Book()}
    changed = 0
    tested_days = 0
    for day in days:
        shift = learn(history)
        if history:
            tested_days += 1

        def learned(r: dict, shift: dict = shift) -> float:
            return min(0.99, max(0.01, r["fair"] + shift.get(r["seg"], 0.0)))
        for recs in by_day[day]:
            if history:
                for r in recs:
                    brier_plain += (r["fair"] - r["won"]) ** 2
                    brier_learned += (learned(r) - r["won"]) ** 2
                    n_brier += 1
                a = pick(recs, lambda r: r["fair"], False)
                b = pick(recs, learned, False)
                c = pick(recs, learned, True)
                if a:
                    books["A"].add(a, a["fair"])
                if b:
                    books["B"].add(b, learned(b))
                if c:
                    books["C"].add(c, learned(c))
                if a and c and a["key"] != c["key"]:
                    changed += 1
            history.extend(recs)

    final = learn(history)
    seg_rows = defaultdict(lambda: [0, 0, 0.0])
    for r in history:
        s = seg_rows[r["seg"]]
        s[0] += 1
        s[1] += r["won"]
        s[2] += r["fair"]
    L = [f"# BOTH SIDES STUDY — {sport.upper()}: every side of every market, bet on or not", "",
         "Written by `backtest/both_sides_study.py` (see its docstring). Every side of every market on every "
         "graded game is a yes/no record: SportyBet's margin-free chance vs what happened. "
         "Corrections are learned walk-forward — each day is judged only on what was learned BEFORE it.", "",
         f"{len(games)} graded {sport} games, {len(history)} yes/no records, {len(days)} match days; "
         f"{tested_days} day(s) tested on what the days before them taught.", "",
         "## Does learning improve the chances?", "",
         "| | Brier score (lower is better) |", "|---|---|"]
    if n_brier:
        L += [f"| SportyBet's chances, margin removed | {brier_plain / n_brier:.5f} |",
              f"| after learning | {brier_learned / n_brier:.5f} |", "",
              f"Over {n_brier} records on the tested days.", ""]
    else:
        L += ["| — | not enough history yet |", ""]
    L += ["## Does learning improve the picks? (£1 a game, price 1.20–2.00, chance 50%+)", "",
          "| Way of picking | picks | won | expected wins | £1 return ± 1 se |", "|---|---|---|---|---|",
          f"| A likeliest outcome, plain chances | {books['A'].line()} |",
          f"| B likeliest outcome, learned chances | {books['B'].line()} |",
          f"| C learned chances, best value within 2 pts | {books['C'].line()} |", "",
          f"C picked a different outcome from A in {changed} game(s).", "",
          "## What has been learned (all days, groups with 50+ records)", "",
          "| outcome @ price band | records | landed | price said | gap | learned shift now |",
          "|---|---|---|---|---|---|"]
    for seg, (n, w, e) in sorted(seg_rows.items(), key=lambda kv: (kv[1][1] - kv[1][2]) / kv[1][0]):
        if n < MIN_N:
            continue
        L.append(f"| {seg} | {n} | {w / n:.1%} | {e / n:.1%} | {(w - e) / n:+.1%} | "
                 f"{final.get(seg, 0.0):+.1%} |")
    return L


def main() -> int:
    every = [r for r in uv.load_graded() if r.get("result")]
    L: list[str] = []
    for sport in ("football", "basketball"):
        L += run(sport, [r for r in every if r.get("sport") == sport]) + [""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
