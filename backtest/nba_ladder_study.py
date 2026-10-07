"""
NBA LADDER STUDY — is SportyBet's ladder spread too narrow or too wide?
(order 41 paper board; Architect 2026-10-07: "build A and B together and C")

Reads every ladder snapshot (output/nba_ladders/*.jsonl, saved by the
evening board and the line watch) and compares the spread each SportyBet
ladder implies (engine/nba_ladder.fit) with the spread real results show
around the sharp line (engine/nba_value, measured in backtest/NBA_STUDY.md
and backtest/NBA_PERIOD_STUDY.md).

A ladder WIDER than reality prices its far lines' long shots too high (the
far Over/Under and big handicaps are worth less than SportyBet thinks, so
their opposite sides pay too much); NARROWER prices the long shots too low.
Either way the far lines, not the centre, are where the value sits, and the
value column says how much — against the measured spread, margin removed.

    python backtest/nba_ladder_study.py     -> backtest/NBA_LADDER_STUDY.md
"""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import nba_ladder as nl  # noqa: E402
from engine import nba_value as nv  # noqa: E402

OUT = ROOT / "backtest" / "NBA_LADDER_STUDY.md"
NAMES = {"225": "Full-game total", "227": "Home points", "228": "Away points",
         "18": "Regulation total", "223": "Full-game handicap", "66": "1st-half handicap",
         "303/q1": "1st-quarter handicap", "303/q2": "2nd-quarter handicap",
         "303/q3": "3rd-quarter handicap", "303/q4": "4th-quarter handicap"}


def measured_sd(key: str) -> float | None:
    """The spread real results show for this market (engine/nba_value)."""
    return nv.MEASURED_SD.get(key)


def far_value(row: dict, key: str, ladder: list[list[float]]) -> list[float]:
    """Value (chance x price - 1) of every side of every line, fair chance from
    the sharp line with the measured spread. Only lines in the board's band."""
    out = []
    sharp = type("S", (), row["sharp"])
    mid = key.split("/")[0]
    q = key.split("/q")[1] if "/q" in key else None
    for line, a, b in ladder:
        if mid in nl.HCP_MARKETS:
            spec = f"hcp={line:g}" + (f"|quarternr={q}" if q else "")
            sides = ((f"Home ({line:+g})", a), (f"Away ({-line:+g})", b))
        else:
            spec = f"total={line:g}"
            sides = ((f"Over {line:g}", a), (f"Under {line:g}", b))
        for desc, price in sides:
            if not nv.BAND[0] <= price <= nv.BAND[1]:
                continue
            p = nv.fair_chance(mid, spec, desc, sharp)
            if p is not None:
                out.append(p * price - 1)
    return out


def main() -> int:
    rows = nl.load()
    L = ["# NBA LADDER STUDY — the spread SportyBet's ladders assume", "",
         "Written by `backtest/nba_ladder_study.py` from every saved SportyBet NBA ladder "
         "(`output/nba_ladders/`). Implied spread = the sd of the Normal curve that best "
         "fits the ladder's margin-free prices (`engine/nba_ladder.fit`).", ""]
    if not rows:
        L.append("No ladder saved yet — NO DATA — PENDING.")
        OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
        print("\n".join(L))
        return 0
    days = sorted({r["at"][:10] for r in rows})
    L += [f"{len(rows)} looks at {len({r['event_id'] for r in rows})} games, {days[0]} to {days[-1]}. "
          "Regular season and preseason are measured apart (preseason rests starters).", ""]
    for stage in ("regular", "preseason"):
        srows = [r for r in rows if r.get("stage") == stage]
        if not srows:
            L += [f"## {stage.capitalize()}", "", "No ladder saved yet — NO DATA — PENDING.", ""]
            continue
        L += [f"## {stage.capitalize()} — {len(srows)} looks at {len({r['event_id'] for r in srows})} games", "",
              "| Market | ladders | implied sd (median) | measured sd | ladder is | value per side in band: median · best |",
              "|---|---|---|---|---|---|"]
        by_key: dict[str, list[tuple[dict, list]]] = {}
        for r in srows:
            for k, lad in r["ladders"].items():
                by_key.setdefault(k, []).append((r, lad))
        for k in sorted(by_key, key=lambda k: list(NAMES).index(k) if k in NAMES else 99):
            fits = [r["fits"].get(k) for r, _ in by_key[k] if r["fits"].get(k)]
            sds = [f[1] for f in fits]
            msd = measured_sd(k)
            imp = median(sds) if sds else None
            verdict = ("PENDING" if imp is None or msd is None else
                       "about right" if abs(imp - msd) / msd < 0.05 else
                       f"WIDER by {imp - msd:.1f}" if imp > msd else f"NARROWER by {msd - imp:.1f}")
            vals = [v for r, lad in by_key[k] for v in far_value(r, k, lad)]
            vs = f"{median(vals):+.1%} · {max(vals):+.1%}" if vals else "—"
            L.append(f"| {NAMES.get(k, k)} | {len(fits)} | {f'{imp:.2f}' if imp else '—'} | "
                     f"{msd if msd else '—'} | {verdict} | {vs} |")
        L.append("")
    L += ["Value uses the board's fair chance (sharp line + measured spread, margin removed); "
          "the board itself still needs +3% (winner) / +5% (lines) and a chance of 50%+ to pick.", ""]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
