"""
PRICE BAND STUDY — what the board's own record says about the price it takes.

WHY THIS EXISTS
  Order 3 said "deploy odds band 1.20-2.00, safest 1.50". The board's own
  graded record does not support "safest": the losses are concentrated where
  the board actually sits, and the one part of the market that has broken even
  in the sweep is the long end the board never reaches. This script computes
  the record from the REAL picks ledgers (output/picks/picks_*.json) every time
  it runs, so the number in front of the Architect is this week's number and
  not a figure typed in once.

WHAT IT MEASURES, per price band and per tier
  n            graded singles (won/lost/void; a void returns the stake)
  landed       share that won, of the ones that stood
  stated       the chance the board stated for them (mean)
  break-even   the share the average price in the band needs to break even
  return       profit/loss per unit staked, flat stakes
  se           one standard error of that return, so "no edge" is visible

  A band whose return is inside +/- 2 se of zero is not evidence either way,
  and says so (HR35: no silent completeness).

    python backtest/price_band_study.py            -> backtest/PRICE_BAND_STUDY.md
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGERS = ROOT / "output" / "picks"
SHARP = ROOT / "data" / "sharp"
OUT = ROOT / "backtest" / "PRICE_BAND_STUDY.md"

BANDS = ((1.00, 1.25), (1.25, 1.30), (1.30, 1.50), (1.50, 2.00), (2.00, 99.0))


def singles(include_study: bool = False) -> list[dict]:
    """Every graded board single in the ledgers (study picks only on request —
    they are a different population and are reported separately)."""
    out = []
    for path in sorted(LEDGERS.glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = list(doc.get("singles") or [])
        if include_study:
            rows += list(doc.get("study") or [])
        for s in rows:
            if s.get("result") in ("won", "lost", "void") and s.get("price"):
                out.append(s)
    return out


def stats(rows: list[dict]) -> dict | None:
    """Flat-stake record of one group. None for an empty group (never 0.0%)."""
    if not rows:
        return None
    void = [r for r in rows if r["result"] == "void"]
    stood = [r for r in rows if r["result"] != "void"]
    won = [r for r in stood if r["result"] == "won"]
    pl = [(r["price"] - 1) if r["result"] == "won" else -1.0 for r in stood]
    n = len(stood)
    ret = sum(pl) / n if n else 0.0
    se = (math.sqrt(sum((x - ret) ** 2 for x in pl) / (n - 1)) / math.sqrt(n)
          if n > 1 else None)
    price = sum(r["price"] for r in stood) / n if n else None
    stated = [r["chance"] for r in stood if r.get("chance") is not None]
    return {"n": n, "void": len(void), "won": len(won),
            "landed": len(won) / n if n else None,
            "stated": sum(stated) / len(stated) if stated else None,
            "price": price, "breakeven": (1 / price) if price else None,
            "ret": ret, "se": se}


def _row(label: str, s: dict | None) -> str:
    if s is None:
        return f"| {label} | 0 | PENDING | PENDING | PENDING | PENDING | no graded pick |"
    se = f" ± {s['se']*100:.1f}" if s["se"] is not None else ""
    if s["se"] is not None and abs(s["ret"]) < 2 * s["se"]:
        verdict = "no edge either way"
    else:
        verdict = "LOSING" if s["ret"] < 0 else "ahead"
    n = f"{s['n']}" + (f" +{s['void']}v" if s["void"] else "")
    stated = f"{s['stated']*100:.1f}%" if s["stated"] is not None else "PENDING"
    return (f"| {label} | {n} | {s['landed']*100:.1f}% | {stated} "
            f"| {s['breakeven']*100:.1f}% | {s['ret']*100:+.1f}%{se} | {verdict} |")


def sharp_rows() -> list[dict]:
    """The parallel sharp-value list's graded picks (monitor/sharp_list.py)."""
    out = []
    for path in sorted(SHARP.glob("sharp_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for p in doc.get("picks") or []:
            if p.get("result") in ("won", "lost", "void") and p.get("price"):
                out.append({"price": p["price"], "result": p["result"],
                            "chance": p.get("sharp_p")})
    return out


def report() -> str:
    board = singles()
    study = [s for path in sorted(LEDGERS.glob("picks_*.json"))
             for s in (json.loads(path.read_text(encoding="utf-8")).get("study") or [])
             if s.get("result") in ("won", "lost", "void") and s.get("price")]
    all_s = stats(board)
    head = ["# PRICE BAND STUDY — the board's record by the price it took",
            "",
            f"Generated {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M')}Z from "
            f"`output/picks/picks_*.json` (graded board singles only; study picks "
            f"and the parallel sharp list are reported separately below).",
            ""]
    if all_s is None:
        return "\n".join(head + ["NO DATA — PENDING: no graded single in the ledgers."])
    head += [f"**All {all_s['n']} graded board singles**: stated "
             f"{all_s['stated']*100:.1f}%, landed {all_s['landed']*100:.1f}% "
             f"(calibration error {(all_s['landed']-all_s['stated'])*100:+.1f} points) "
             f"at an average price of {all_s['price']:.3f}, which needs "
             f"{all_s['breakeven']*100:.1f}% to break even. Return "
             f"{all_s['ret']*100:+.1f}%"
             + (f" ± {all_s['se']*100:.1f}." if all_s["se"] else "."),
             "",
             "The prediction is not the problem. The price is.",
             "",
             "## By price band",
             "",
             "| band | n | landed | stated | break-even | return / unit | reading |",
             "|---|---|---|---|---|---|---|"]
    for lo, hi in BANDS:
        rows = [s for s in board if lo <= s["price"] < hi]
        head.append(_row(f"{lo:.2f}–{hi:.2f}" if hi < 99 else "2.00+", stats(rows)))
    head += ["", "## By tier", "",
             "| tier | n | landed | stated | break-even | return / unit | reading |",
             "|---|---|---|---|---|---|---|"]
    for tier in sorted({(s.get("tier") or "—") for s in board}):
        head.append(_row(tier, stats([s for s in board if (s.get("tier") or "—") == tier])))
    head += ["", "## The other two populations", "",
             "| list | n | landed | stated | break-even | return / unit | reading |",
             "|---|---|---|---|---|---|---|",
             _row("study picks (demoted, not sent)", stats(study)),
             _row("sharp value list (parallel test)", stats(sharp_rows())),
             "",
             "The sharp list takes a price only when SportyBet pays MORE than the "
             "Betfair Exchange's fair odds (`engine/sharp_value.py`), with no "
             "most-likely-outcome and no 50% floor. It is the control for the "
             "price question: same days, same fixtures, same grader.",
             "",
             "## What this does and does not establish",
             "",
             "A band's return is evidence only when it is outside ± 2 standard "
             "errors of zero; the table says so per row. Nothing here is a "
             "demonstrated edge, and a row marked PENDING has no graded pick yet "
             "(HR35).", ""]
    return "\n".join(head)


def main() -> int:
    text = report()
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
