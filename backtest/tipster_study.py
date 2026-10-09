"""
TIPSTER STUDY — what the slips tipsters post on X actually return (Architect
2026-10-08, via the coordinator session). Reads graded slips (engine/tipsters.py)
from a folder and writes TIPSTER_STUDY.md next to them:
  1. per poster: slips, legs, how often slips and legs landed against the chance
     their prices implied, £1 return per slip with its standard error;
  2. legs by market and by price band;
  3. consensus: does a game that appears on several slips that day land more often?
  4. official "Top Picks" codes vs everyone else, against the bookmaker's margin.
Implied chance = 1 / price, margin INCLUDED (a slip shows only the chosen
price), so a fairly priced leg lands a little MORE often than implied — the
margin-free bar is ~5% above it. Same bar as the paper book: nothing is trusted
before 100+ slips, and nothing is promoted without the Architect. Paper only.

    python backtest/tipster_study.py --dir <folder>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import tipsters as tp  # noqa: E402

MIN_SLIPS = 100
BANDS = ((1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 3.0), (3.0, 1000.0))


def _se(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("inf")
    m = sum(xs) / len(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def _slip_row(name: str, slips: list[dict]) -> str:
    g = [s for s in slips if s["status"] in ("won", "lost")]
    if not g:
        return f"| {name} | {len(slips)} | — | — | — | — |"
    pnl = [s["payout"] - 1 for s in g]
    won = sum(s["status"] == "won" for s in g)
    legs = [leg for s in g for leg in s["legs"] if leg.get("result") in ("win", "lose", "half_win", "half_lose")]
    lw = sum(leg["result"] in ("win", "half_win") for leg in legs)
    imp = sum(s["implied"] for s in g) / len(g)
    return (f"| {name} | {len(slips)} ({len(g)} graded) | {won}/{len(g)} landed vs {imp:.1%} implied | "
            f"{lw}/{len(legs)} legs | {sum(pnl) / len(pnl):+.0%} ± {_se(pnl):.0%} | "
            f"{'learning' if len(g) < MIN_SLIPS else 'enough to judge'} |")


def write(folder: Path, out: Path) -> str:
    slips = tp.load_graded(folder)
    L = ["# TIPSTER STUDY — slips posted on X, graded", "",
         "Written by `backtest/tipster_study.py` from graded slips (`engine/tipsters.py`). Implied chance = "
         "1 / price with the bookmaker's margin included — a fairly priced leg lands ~5% more often than that. "
         f"Nothing is trusted before {MIN_SLIPS}+ graded slips; nothing is promoted without the Architect. Paper only.", ""]
    if not slips:
        L.append("No graded slip yet — NO DATA — PENDING.")
        out.write_text("\n".join(L) + "\n", encoding="utf-8")
        return "\n".join(L)
    graded = [s for s in slips if s["status"] in ("won", "lost")]
    L += [f"{len(slips)} slips looked at: {len(graded)} graded, "
          f"{sum(s['status'] == 'ungradable' for s in slips)} ungradable (a leg's result or market couldn't be read).", "",
          "## Per poster", "", "| Poster | slips | slips landed | legs landed | £1 a slip: return ± se | verdict |",
          "|---|---|---|---|---|---|"]
    by_poster: dict[str, list[dict]] = defaultdict(list)
    for s in slips:
        by_poster[s["poster"] or "?"].append(s)
    for p in sorted(by_poster, key=lambda p: -len(by_poster[p])):
        L.append(_slip_row(p, by_poster[p]))
    legs = [leg for s in graded for leg in s["legs"] if leg.get("result") in ("win", "lose", "half_win", "half_lose")]
    L += ["", "## Legs by market", "", "| Market | legs | landed | implied (avg) |", "|---|---|---|---|"]
    by_m: dict[str, list[dict]] = defaultdict(list)
    for leg in legs:
        by_m[f"{leg['sport']} {leg['market']}"].append(leg)
    for k in sorted(by_m, key=lambda k: -len(by_m[k])):
        xs = by_m[k]
        L.append(f"| {k} | {len(xs)} | {sum(x['result'] in ('win', 'half_win') for x in xs) / len(xs):.0%} | "
                 f"{sum(1 / x['price'] for x in xs) / len(xs):.0%} |")
    L += ["", "## Legs by price band", "", "| Price | legs | landed | implied (avg) |", "|---|---|---|---|"]
    for lo, hi in BANDS:
        xs = [x for x in legs if lo <= x["price"] < hi]
        if xs:
            L.append(f"| {lo:.2f}–{hi:.2f} | {len(xs)} | {sum(x['result'] in ('win', 'half_win') for x in xs) / len(xs):.0%} | "
                     f"{sum(1 / x['price'] for x in xs) / len(xs):.0%} |")
    count: dict[tuple[str, str, str], int] = defaultdict(int)
    for s in graded:
        for game in {(s["posted_at"][:10], (leg.get("home") or "").lower(), (leg.get("away") or "").lower())
                     for leg in s["legs"]}:
            count[game] += 1
    L += ["", "## Consensus — a game on several slips the same day", "",
          "| Slips carrying the game | legs | landed | implied (avg) |", "|---|---|---|---|"]
    for lo, hi, name in ((1, 2, "1"), (2, 3, "2"), (3, 999, "3+")):
        xs = [leg for s in graded for leg in s["legs"]
              if leg.get("result") in ("win", "lose", "half_win", "half_lose")
              and lo <= count[(s["posted_at"][:10], (leg.get("home") or "").lower(), (leg.get("away") or "").lower())] < hi]
        if xs:
            L.append(f"| {name} | {len(xs)} | {sum(x['result'] in ('win', 'half_win') for x in xs) / len(xs):.0%} | "
                     f"{sum(1 / x['price'] for x in xs) / len(xs):.0%} |")
    L += ["", "## Legs by class — aligned vs risky add-ons", "",
          "aligned = a plain market at 60%+ implied (≤ 1.67, the kind of leg our F8/F1/F2/B1 rules bet); "
          "special = a SportyBet special we grade (1UP/2UP early payout, \"or Over 2.5\", win either half, "
          "3 in a row) at 2.00 or shorter; risky = a price over 2.00 or a market we can't read; "
          "middle = the rest.", "",
          "| Class | legs | landed | implied (avg) | ungradable |", "|---|---|---|---|---|"]
    agg: dict = {"slips_graded": len(graded), "classes": {}}
    all_legs = [tp.remap(leg) for s in slips for leg in s["legs"]]
    for cls in ("aligned", "middle", "special", "risky"):
        xs = [x for x in all_legs if tp.leg_class(x) == cls]
        gx = [x for x in xs if x.get("result") in ("win", "lose", "half_win", "half_lose")]
        if not xs:
            continue
        landed = sum(x["result"] in ("win", "half_win") for x in gx)
        imp = sum(1 / x["price"] for x in gx) / len(gx) if gx else None
        L.append(f"| {cls} | {len(xs)} | {f'{landed}/{len(gx)} = {landed / len(gx):.0%}' if gx else '—'} | "
                 f"{f'{imp:.0%}' if imp else '—'} | {len(xs) - len(gx)} |")
        agg["classes"][cls] = {"legs": len(xs), "graded": len(gx), "landed": landed, "implied_avg": imp}
    kept = []
    for s in graded:
        al = [x for x in s["legs"] if tp.leg_class(x) == "aligned"]
        if al and all(x.get("result") in ("win", "lose", "half_win", "half_lose", "push") for x in al):
            kept.append(all(x["result"] in ("win", "half_win", "push") for x in al))
    if kept:
        L += ["", f"Counterfactual — the same slips with ONLY their aligned legs: {sum(kept)}/{len(kept)} would have "
              f"landed (as posted: {sum(s['status'] == 'won' for s in graded)}/{len(graded)})."]
        agg["aligned_only_slips"] = {"landed": sum(kept), "of": len(kept)}
    # nameless aggregates only — the one output that may feed the framework's learning
    (out.parent / "aggregates.json").write_text(json.dumps(agg, indent=1), encoding="utf-8")
    L += ["", "## Official Top Picks vs everyone else", "",
          "| Source | slips | slips landed | legs landed | £1 a slip: return ± se | verdict |", "|---|---|---|---|---|---|"]
    L.append(_slip_row("official (@SportyBet / @SportyBetNG)", [s for s in slips if s["official"]]))
    L.append(_slip_row("tipsters", [s for s in slips if not s["official"]]))
    L += ["", "A bookmaker's margin of ~5% a leg compounds on an acca: 6 legs at fair prices still return about "
          "−26% on average, so a long acca slip must beat that just to break even.", ""]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="folder holding slips_*.jsonl (and decoded_/graded_ files)")
    ap.add_argument("--out", help="where to write the study (default: <dir>/TIPSTER_STUDY.md)")
    a = ap.parse_args(argv)
    folder = Path(a.dir)
    print(write(folder, Path(a.out) if a.out else folder / "TIPSTER_STUDY.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
