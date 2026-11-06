"""
RUGBY market catalogue check (framework#344, record-only).

The #344 checklist asks for "every option a yes/no bet, both sides weighed". This lists every rugby market the
multi-sport board asks SportyBet for (engine/multisport.py SPORTS["rugby"]["markets"]) and proves, over a grid of
final scores, that the settler grades the sides of each market so that exactly one side wins (or the bet is void):
a market whose sides could both win, or both lose, would corrupt every graded record and the learning built on it.
The scores are a logic grid (every home/away score pair), not fixtures or prices; nothing is invented about a game.

Record only: nothing here changes a stake, bar, threshold or the live switch.

  python backtest/rugby_markets_study.py      writes backtest/RUGBY_MARKETS_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_MARKETS_STUDY.md"
SCORES = [(h, a) for h in range(0, 71) for a in range(0, 71)]
# market id -> (name, list of (spec, [sides]))   every market asked for in SPORTS["rugby"]["markets"]
CATALOGUE = {
    "1": ("1X2 (80 min)", [("", ["Home", "Draw", "Away"])]),
    "406": ("Winner incl. extra time", [("", ["Home", "Away"])]),
    "10": ("Double chance", [("", ["Home or Draw", "Home or Away", "Draw or Away"])]),
    "11": ("Draw no bet", [("", ["Home", "Away"])]),
    "16": ("Handicap (Asian, half and whole lines)",
           [(f"hcp={h:g}", [f"Home ({h:g})", f"Away ({-h:g})"]) for h in (-30.5, -10.5, -7, -2.5, 3, 12.5)]),
    "14": ("3-way handicap", [("hcp=0:10", ["Home (0:10)", "Draw (0:10)", "Away (0:10)"]),
                              ("hcp=10:0", ["Home (10:0)", "Draw (10:0)", "Away (10:0)"])]),
    "18": ("Total points over/under", [(f"total={t:g}", ["Over", "Under"]) for t in (35.5, 45.5, 55.5, 60)]),
}


def _result(h: int, a: int) -> dict:
    return {"final": (h, a), "periods": [], "winner": 1 if h > a else 2 if a > h else None}


def check(mid: str, specs: list) -> dict:
    """Over every score: count games where the settled sides contradict (two winners, or none without a void)."""
    bad = 0
    voids = 0
    for h, a in SCORES:
        r = _result(h, a)
        for spec, sides in specs:
            got = [ms.settle("rugby", mid, spec, s, r) for s in sides]
            if any(g is None for g in got):
                voids += 1
                continue
            wins = sum(got)
            ok = wins == 2 if mid == "10" else wins == 1   # double chance: two of three bets win
            bad += 0 if ok else 1
    return {"bad": bad, "voids": voids, "cells": len(SCORES) * len(specs)}


def exchange_covered(mid: str, specs: list) -> str:
    keys = [f"rugby:{mid}|{spec}|{s}" for spec, sides in specs for s in sides]
    n = sum(1 for k in keys if ms.canonical(k))
    return f"{n}/{len(keys)} sides have an exchange price key"


def run() -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cfg = ms.SPORTS["rugby"]
    asked = cfg["markets"].split(",")
    L = ["# Rugby market catalogue check", "",
         f"Made {now} by `backtest/rugby_markets_study.py` (framework#344). Asks SportyBet for markets "
         f"{', '.join(asked)}; Matchbook event types {cfg['mb']}. Logic grid of {len(SCORES)} final scores "
         "(0-70 each), not fixtures.", "",
         "| Market | Name | Sides graded | Contradictions | Void cells | Exchange price keys |", "|---|---|---|---|---|---|"]
    total_bad = 0
    for mid in asked:
        if mid not in CATALOGUE:
            L.append(f"| {mid} | NOT IN CATALOGUE | - | PENDING | PENDING | - |")
            total_bad += 1
            continue
        name, specs = CATALOGUE[mid]
        c = check(mid, specs)
        total_bad += c["bad"]
        L.append(f"| {mid} | {name} | {sum(len(s) for _, s in specs)} | {c['bad']} | {c['voids']} | "
                 f"{exchange_covered(mid, specs)} |")
    L += ["", "## Reading", "",
          ("- Every market the board asks for settles as exactly one winning side (double chance: two of three), "
           "or void; both sides are weighed on the same result." if total_bad == 0
           else f"- {total_bad} contradictions: the settler must be fixed before the record can be trusted."),
          f"- The model prices only the winner market (id {cfg['winner']}); the other markets are recorded and "
          "graded, and shadowed by backtest/RUGBY_TOTALS_STUDY.md and RUGBY_MARGIN_STUDY.md.",
          "- Whole-number lines can push (void); the exchange key exists only for half lines, so whole lines stay "
          "on paper without an exchange price.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    text = run()
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
