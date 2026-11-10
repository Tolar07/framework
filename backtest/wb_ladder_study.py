"""
WORLD BASKETBALL LADDER STUDY - twin of backtest/nba_ladder_study.py for NCAA and the other world leagues
(framework#397). RECORD-ONLY: a study, not a selector.

Reads the every-market record (output/world_basketball/wb_markets_*.jsonl, engine/wb_markets.py), takes each
game's last look before tip-off, fits every points ladder (engine/wb_ladder, the NBA fit reused) and compares
the spread SportyBet's ladder assumes with the spread real NCAA results show around ESPN's line. Also: how far
each ladder's centre sits from the sharp line, and one game-shape example (engine/wb_ladder.shape).
Leagues with no sharp line (EuroLeague / FIBA) get the ladder fit but no centre check: PENDING (HR35).

    python backtest/wb_ladder_study.py      -> backtest/WB_LADDER_STUDY.md
"""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import wb_ladder as wl  # noqa: E402
from engine import wb_markets as wm  # noqa: E402

OUT = ROOT / "backtest" / "WB_LADDER_STUDY.md"
NAMES = {"225": "Full-game total", "227": "Home points", "228": "Away points", "18": "Regulation total",
         "68": "1st-half total", "223": "Full-game handicap", "66": "1st-half handicap"}


def centre_gap(key: str, centre: float, sharp: dict | None) -> float | None:
    """Ladder centre minus the sharp line (full-game total / home margin only), else None."""
    if not sharp:
        return None
    if key == "225" and sharp.get("total") is not None:
        return centre - sharp["total"]
    if key == "223" and sharp.get("spread") is not None:
        return centre - (-sharp["spread"])
    return None


def build(looks: list[dict]) -> list[str]:
    L = ["# WORLD BASKETBALL LADDER STUDY - the spread SportyBet's ladders assume", "",
         "Written by `backtest/wb_ladder_study.py` from the last pre-tip look at each game in "
         "`output/world_basketball/wb_markets_*.jsonl`. Implied spread = the sd of the Normal curve that best "
         "fits a ladder's margin-free prices (`engine/nba_ladder.fit`, reused). Measured spread = the NCAA "
         "curves in `engine/ncaa_lines.py`. Record only: no pick, stake or threshold reads this.", ""]
    if not looks:
        return L + ["No every-market look saved yet - NO DATA - PENDING.", ""]
    by: dict[str, list[tuple[dict, tuple]]] = {}
    for r in looks:
        for k, f in wl.fits(r.get("markets") or []).items():
            if f:
                by.setdefault(k, []).append((r, f))
    L += [f"{len(looks)} games with a last look. Ladders with under 3 usable lines are not fitted.", "",
          "| Market | ladders | implied sd (median) | measured sd | ladder is | centre v sharp line (median, n) |",
          "|---|---|---|---|---|---|"]
    for k in sorted(by, key=lambda k: list(NAMES).index(k) if k in NAMES else 99):
        imp = median(f[1] for _, f in by[k])
        msd = wl.MEASURED_SD.get(k)
        gaps = [g for r, f in by[k] if (g := centre_gap(k, f[0], r.get("sharp"))) is not None]
        gs = f"{median(gaps):+.2f} (n={len(gaps)})" if gaps else "PENDING"
        L.append(f"| {NAMES.get(k, k)} | {len(by[k])} | {imp:.2f} | {msd if msd else 'PENDING'} | "
                 f"{wl.verdict(imp, msd)} | {gs} |")
    if not by:
        L.append("| - | 0 | - | - | PENDING | PENDING |")
    sh = next((wl.shape(r["sharp"].get("total"), r["sharp"].get("spread")) for r in looks
               if r.get("sharp")), None)
    L += ["", "Game shape (label only), first game with a sharp line: "
          + (f"typical {sh['score'][0]}-{sh['score'][1]}" if sh else "PENDING - no sharp line recorded yet"), ""]
    return L


def main() -> int:
    L = build(wm.last_looks(wm.load()))
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
