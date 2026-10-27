"""
HINDSIGHT backfill (2026-10-13): the team profiles of 13 Oct put onto every
graded universe game since 7 Oct, to see what the reads would have said.

NOT a test of the P rules: the season stats the profiles were built from
already include these games, so it flatters the reads. The real test is the
paper book from 2026-10-13, on profiles attached before kick-off.

    python data/study/2026-10-13/profile_backfill.py   → profile_backfill.md
"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import profile_study as ps  # noqa: E402

from data import flashscore_results as fr  # noqa: E402
from data import team_profiles as tp  # noqa: E402
from engine import paper_book as pb  # noqa: E402
from engine import universe as uv  # noqa: E402


def main() -> None:
    db = tp.load()
    idx = [(lg, t) for lg, b in db["leagues"].items() for t in b.get("teams") or []]
    memo: dict = {}

    def best(name):           # strict and unique, as the graders match names
        if name not in memo:
            sc = sorted(((max(fr._sim(name, t.get("name") or ""), fr._sim(name, t.get("short") or "")), lg, t)
                         for lg, t in idx), key=lambda x: -x[0])
            ok = sc and sc[0][0] >= fr.MATCH_MIN and (len(sc) < 2 or sc[1][0] < sc[0][0]
                                                       or sc[1][2].get("id") == sc[0][2].get("id"))
            memo[name] = (sc[0][1], sc[0][2]) if ok else None
        return memo[name]
    rows = [r for r in uv.load_graded() if r.get("result") and r.get("sport") == "football"]
    out = []
    for r in rows:
        h, a = best(r["home"]), best(r["away"])
        if not h or not a or (h[0] != a[0] and h[0] not in tp.EUROPEAN and a[0] not in tp.EUROPEAN):
            continue
        out.append({**r, "profile": {"read": tp.profile_read(h[1], a[1])}})
    for k in pb.SINCE:
        if k.startswith("P"):
            pb.SINCE[k] = ""
    agg = defaultdict(list)
    for r in out:
        for b in pb.bets(r):
            if b["strategy"].startswith("P"):
                agg[b["strategy"]].append(b)
    lines = ["# HINDSIGHT — 13 Oct team profiles on games graded 7-13 Oct", "",
             "**Not a test**: the profiles' season stats include these games. The real test is the "
             "paper book from 2026-10-13 (profiles attached before kick-off).", "",
             f"Graded football games {len(rows)}; both teams matched in the 29 profiled competitions: {len(out)}.", "",
             "## The P rules (first price, £1 flat)", "", "| Rule | Bets | Won | SportyBet fair | Avg price | P/L | ROI |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for k, bs in sorted(agg.items()):
        n = len(bs)
        lines.append(f"| {k} | {n} | {sum(b['won'] for b in bs) / n:.0%} | {sum(b['fair'] for b in bs) / n:.0%} | "
                     f"{sum(b['price'] for b in bs) / n:.2f} | {sum(b['pnl'] for b in bs):+.2f}u | "
                     f"{sum(b['pnl'] for b in bs) / n:+.1%} |")
    body = ps.build(out).split("\n", 1)[1]
    (Path(__file__).parent / "profile_backfill.md").write_text("\n".join(lines) + "\n\n" + body, encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
