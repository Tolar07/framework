"""
RUGBY Elo-variants walk-forward study (framework#344, record-only SHADOW candidates).

backtest/rugby_calibration_study.py found home sides win ~9% more than the Elo says. Why? Two candidate fixes, both
tried next to the live Elo on the same ESPN games, every setting counted, chosen on 2014-2019, reported on 2020+ only:

  A. a bigger / per-league home edge (home Elo points per league, from a grid) ;
  B. margin-of-victory Elo: the update is scaled by ln(1 + |margin|) (the idea used by 538-style Elo; re-implemented
     here from the idea, no outside code), because a 40-point win says more than a 1-point win.

Record only: nothing here changes a stake, bar, threshold or the live switch.

  python backtest/rugby_inputs_study.py      writes backtest/RUGBY_INPUTS_STUDY.md
"""
from __future__ import annotations

import itertools
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_INPUTS_STUDY.md"
HOME_GRID = (0.0, 70.0, 100.0, 130.0, 160.0, 200.0)
MOV = (False, True)
K = 32.0
MIN_N = 100


def replay(games, home_by_league, mov: bool, k: float = K):
    """Elo chance of a home win BEFORE each game (None until both sides have MIN_GAMES games), then learn."""
    r, n, out = {}, {}, []
    for g in games:
        h, a = g["home"], g["away"]
        rh, ra = r.get(h, rb.ELO_START), r.get(a, rb.ELO_START)
        e = 1 / (1 + 10 ** ((ra - rh - home_by_league[g["league"]]) / 400))
        out.append(e if n.get(h, 0) >= rb.MIN_GAMES and n.get(a, 0) >= rb.MIN_GAMES else None)
        scale = math.log(1 + abs(g["hs"] - g["as"])) if mov and "hs" in g else 1.0
        if mov and scale == 0:
            scale = 1.0   # a draw still teaches (y = 0.5)
        d = k * scale * (g["y"] - e)
        r[h], r[a] = rh + d, ra - d
        n[h], n[a] = n.get(h, 0) + 1, n.get(a, 0) + 1
    return out


def best_home_by_league(games, mov: bool):
    """Per league, the home edge with the lowest tuning-year Brier (each league tried on the grid, others fixed at 70)."""
    leagues = sorted({g["league"] for g in games})
    chosen = {lg: 70.0 for lg in leagues}
    tries = 0
    for lg in leagues:
        scores = {}
        for h in HOME_GRID:
            trial = dict(chosen, **{lg: h})
            ev = rb.evaluate(games, replay(games, trial, mov), rb.TUNE_YEARS)
            tries += 1
            if ev["n"] >= MIN_N:
                scores[h] = ev["brier"]
        if scores:
            chosen[lg] = min(scores, key=scores.get)
    return chosen, tries


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    leagues = sorted({g["league"] for g in games})
    flat = lambda h: {lg: h for lg in leagues}  # noqa: E731
    rows, tries = [], 0
    live = rb.evaluate(games, rb.replay(games, 24.0, 0.0), test, base)
    rows.append(("Live board: K24, no home edge", live))
    tuned_flat = rb.evaluate(games, replay(games, flat(70.0), False), test, base)
    tries += 1
    rows.append(("K32, flat home +70 (backtest's pick)", tuned_flat))
    picks = {}
    for mov in MOV:
        by, t = best_home_by_league(games, mov)
        tries += t
        picks[mov] = by
        label = ("MOV Elo" if mov else "Plain Elo") + ", per-league home " + ", ".join(f"{lg} +{h:.0f}" for lg, h in by.items())
        rows.append((label, rb.evaluate(games, replay(games, by, mov), test, base)))
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby Elo variants (per-league home edge, margin-of-victory)", "",
         f"Made {made} by `backtest/rugby_inputs_study.py` (framework#344). {len(games)} games, final scores only "
         f"(ESPN). Settings tried: **{tries}**; chosen on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on "
         f"**{test[0]}-{test[1]} only**.", "",
         f"| Rule (held-out years) | Games | Brier | Brier flat baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|"]
    for name, r in rows:
        if r["n"]:
            L.append(f"| {name} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |")
        else:
            L.append(f"| {name} | 0 | PENDING | PENDING | PENDING |")
    L += ["", "## Reading", ""]
    ok = [(nm, r) for nm, r in rows if r["n"]]
    if len(ok) == len(rows):
        best_nm, best_r = min(ok, key=lambda x: x[1]["brier"])
        gain = live["brier"] - best_r["brier"]
        L.append(f"- Best held-out Brier: {best_nm} at {best_r['brier']:.4f} vs {live['brier']:.4f} for the live "
                 f"setting ({gain:+.4f}). " + ("A shadow candidate, to be confirmed on the shadow board's own record."
                                               if gain > 0.0005 else "No gain worth a shadow."))
        mv_gain = rows[2][1]["brier"] - rows[3][1]["brier"]
        L.append(f"- Margin-of-victory scaling changed held-out Brier by {mv_gain:+.4f} "
                 + ("(helps)." if mv_gain > 0.0005 else "(no real help)."))
    L += [f"- {tries} settings tried; the held-out line is the honest one.",
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
