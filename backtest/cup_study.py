"""
TURKISH CUP STUDY — what the archived cup ties show (Architect 2026-10-07:
"study each of the fixtures, study the outcome and use it for training the
model and training yourself").

Reads data/cups/results.json (data/european_archive.archive_cups, filled by
every daily run from Flashscore) and writes backtest/TURKISH_CUP_STUDY.md:
how often a tie is level after 90 minutes, goals, half-time leads, home
advantage, and whether the higher division goes through. A tie that went to
extra time has no reliable 90-minute score in the feed, so it counts only as
"level after 90" (HR35 / ID48).

    python backtest/cup_study.py
"""
from __future__ import annotations

import json
import sys
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import european_archive as ea  # noqa: E402

OUT = ROOT / "backtest" / "TURKISH_CUP_STUDY.md"
DIV = {1: "Super Lig", 2: "1. Lig", 3: "2. Lig", 4: "3. Lig", None: "no league table (amateur?)"}


def _ci(k: int, n: int) -> str:
    """Share with a 95% Wilson interval — small samples say how little they know."""
    if n == 0:
        return "—"
    p, z = k / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{k}/{n} = {p:.0%} (95% range {max(0, c - h):.0%}–{min(1, c + h):.0%})"


def main() -> int:
    rows = json.loads(ea.CUP_PATH.read_text(encoding="utf-8")) if ea.CUP_PATH.exists() else []
    L = ["# TURKISH CUP STUDY", "",
         "Written by `backtest/cup_study.py` from `data/cups/results.json` (Flashscore, archived by "
         "every daily run). Divisions are read from the same week's league results.", ""]
    if not rows:
        L.append("No cup tie archived yet — NO DATA — PENDING.")
        OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
        print("\n".join(L))
        return 0
    reg = [r for r in rows if not r["went_to_et"]]
    n, m = len(rows), len(reg)
    goals = [r["fthg"] + r["ftag"] for r in reg]
    lead = [r for r in reg if r["fh_home"] is not None and r["fh_home"] != r["fh_away"]]
    held = sum((r["fh_home"] > r["fh_away"]) == (r["fthg"] > r["ftag"]) for r in lead)
    rounds = sorted({r["competition"] for r in rows})
    L += [f"{n} ties, {rows[0]['date']} to {rows[-1]['date']} — {', '.join(rounds)}.", "",
          "## What happened", "",
          f"- Level after 90 minutes (extra time / penalties): {_ci(n - m, n)}",
          f"- Home side won in 90: {_ci(sum(r['fthg'] > r['ftag'] for r in reg), n)}",
          f"- Away side won in 90: {_ci(sum(r['fthg'] < r['ftag'] for r in reg), n)}",
          f"- Goals per 90 minutes (ties decided in 90): {sum(goals) / m:.2f}" if m else "- Goals: —",
          f"- Over 1.5: {_ci(sum(g > 1 for g in goals), m)}",
          f"- Over 2.5: {_ci(sum(g > 2 for g in goals), m)}",
          f"- Both teams scored: {_ci(sum(r['fthg'] > 0 and r['ftag'] > 0 for r in reg), m)}",
          f"- Half-time leader won: {_ci(held, len(lead))}", "",
          "## Division gaps", ""]
    gap = [r for r in rows if r["home_tier"] != r["away_tier"]]
    hi_won = hi_lost = et = 0
    for r in gap:
        h, a = r["home_tier"] or 9, r["away_tier"] or 9          # no table = lowest
        if r["went_to_et"]:
            et += 1
        elif (r["fthg"] > r["ftag"]) == (h < a):
            hi_won += 1
        else:
            hi_lost += 1
    L += [f"Ties between different divisions (a club in no league table counted lowest): {len(gap)}. "
          f"Higher division won in 90: {hi_won}, lost: {hi_lost}, level after 90: {et}.", "",
          "| Date | Home (division) | Score | Away (division) | |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['date']} | {r['home']} ({DIV.get(r['home_tier'], r['home_tier'])}) | "
                 f"{r['fthg']}–{r['ftag']}{' (incl. ET)' if r['went_to_et'] else ''} | "
                 f"{r['away']} ({DIV.get(r['away_tier'], r['away_tier'])}) | "
                 f"{'level after 90' if r['went_to_et'] else ''} |")
    L += ["", "## What it can and can't do yet", "",
          "- The framework does not price the Turkish Cup (only the Super Lig is covered), and "
          "SportyBet did not list most qualification ties — they could not have been bet.",
          "- A sample this small sets priors, not a model: the 95% ranges above are wide. "
          "Each daily run adds the week's ties; the rounds with Super Lig clubs (which SportyBet "
          "does list) are the ones that matter for picks.", ""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
