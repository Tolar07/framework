"""STAT LINES STUDY: do SportyBet's corners, bookings and 1st-half total prices pay, and do the stats claims beat them?

Reads data/stat_lines/graded/*.jsonl (engine/stat_lines.py) and data/world_facts_detail/*.jsonl.
Two questions, each with its sample size and a 90% range; nothing is judged before 300 graded lines:
1. The price alone: per market and side, the hit rate against the price's own chance (de-vigged) and the ROI
   at SportyBet's last price before kick-off. This is the margin a stats bet has to overcome.
2. The claim: backtest/STATS_CLAIMS_PROOF.md found teams' corner and card counts repeat from game to game.
   Here: the two teams' average corners (or yellow cards) in their last 5 matches in our archive, summed,
   against the line. Bet over when that sum is 1.5+ above the line, under when 1.5+ below. ROI at the price.
RECORD ONLY. Writes output/stat_lines/STAT_LINES_STUDY.md (framework-data).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_JUDGE = 300
STAT_OF = {"corners": "corners", "bookings": "yellow"}


def _rows(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def roi_range(rets: list[float]):
    if not rets:
        return None, None, None
    n = len(rets)
    m = sum(rets) / n
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / max(1, n - 1))
    h = 1.645 * sd / math.sqrt(n)
    return m, m - h, m + h


def team_history(detail: list[dict]) -> dict:
    """{team: [(ko, {"corners": n, "yellow": n}), ...]} from the world_facts detail archive."""
    h = defaultdict(list)
    for d in detail:
        st = ((d.get("stats") or {}).get("match") or {})
        for side, team in ((0, d["home"]), (1, d["away"])):
            vals = {k: st[k][0] + st[k][1] for k in ("corners", "yellow") if k in st and None not in st[k]}
            if vals:
                h[team].append((d["ko"], vals))
    for v in h.values():
        v.sort(key=lambda x: x[0])
    return h


def recent(hist: dict, team: str, ko: str, stat: str, n: int = 5):
    vals = [v[stat] for t, v in hist.get(team, []) if t < ko and stat in v][-n:]
    return sum(vals) / len(vals) if len(vals) == n else None


def fmt(m, lo, hi):
    return "PENDING" if m is None else f"{100 * m:+.1f}% ({100 * lo:+.1f}% to {100 * hi:+.1f}%)"


def main(root: Path = ROOT) -> str:
    graded = [r for r in _rows(root / "data" / "stat_lines" / "graded") if r.get("graded")]
    detail = _rows(root / "data" / "world_facts_detail")
    hist = team_history(detail)
    price = defaultdict(lambda: {"rets": [], "hits": 0, "p": 0.0})
    claim = defaultdict(list)
    for r in graded:
        for mkt, lines in r["graded"].items():
            for ln, res in lines.items():
                o, u = r["last"]["lines"][mkt][ln]
                q_over = (1 / o) / (1 / o + 1 / u)
                for side, px, q in (("over", o, q_over), ("under", u, 1 - q_over)):
                    if res[side] is None:
                        continue
                    k = (mkt, side)
                    price[k]["rets"].append(px - 1 if res[side] else -1.0)
                    price[k]["hits"] += res[side]
                    price[k]["p"] += q
                stat = STAT_OF.get(mkt)
                if stat and res["over"] is not None:
                    a, b = recent(hist, r.get("fs_home") or r["home"], r["ko"], stat), recent(hist, r.get("fs_away") or r["away"], r["ko"], stat)
                    if a is None or b is None:
                        continue
                    gap = a + b - float(ln)
                    if gap >= 1.5:
                        claim[mkt].append(o - 1 if res["over"] else -1.0)
                    elif gap <= -1.5:
                        claim[mkt].append(u - 1 if res["under"] else -1.0)
    L = ["# STAT LINES STUDY (record only)\n",
         f"{len(graded)} matches graded with SportyBet's own corners / bookings / 1st-half total lines "
         f"(`engine/stat_lines.py`). Nothing is judged before {MIN_JUDGE} bets in a row of the table.\n",
         "## 1. The price alone (ROI at SportyBet's last price before kick-off, 90% range)\n",
         "| market | side | bets | hit | price's own chance | ROI | judged? |", "|---|---|---|---|---|---|---|"]
    for (mkt, side), d in sorted(price.items()):
        n = len(d["rets"])
        m, lo, hi = roi_range(d["rets"])
        L.append(f"| {mkt} | {side} | {n} | {100 * d['hits'] / n:.1f}% | {100 * d['p'] / n:.1f}% | {fmt(m, lo, hi)} | "
                 f"{'yes' if n >= MIN_JUDGE else 'PENDING (too few)'} |")
    L += ["\n## 2. The claim: last-5 average of both teams vs the line (gap 1.5+)\n",
          "| market | bets | ROI | judged? |", "|---|---|---|---|"]
    for mkt in ("corners", "bookings"):
        rets = claim.get(mkt, [])
        m, lo, hi = roi_range(rets)
        L.append(f"| {mkt} | {len(rets)} | {fmt(m, lo, hi)} | {'yes' if len(rets) >= MIN_JUDGE else 'PENDING (too few)'} |")
    L.append("\nTeam history comes from the world_facts detail archive (from 12 Nov 2026), so the claim column fills "
             "as both teams build 5 recorded matches.")
    out = root / "output" / "stat_lines" / "STAT_LINES_STUDY.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return f"stat lines study: {len(graded)} graded matches, claim bets corners {len(claim.get('corners', []))}, bookings {len(claim.get('bookings', []))}"


if __name__ == "__main__":
    print(main())
