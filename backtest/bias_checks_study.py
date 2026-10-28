"""
BIAS CHECKS STUDY — to-do #7 idea 2, measured walk-forward (recorded only, no stakes).

For every day of the later half of the universe, the (market, price band) table is built from games
that kicked off BEFORE that day only (engine/bias_checks.table), and each side priced that day is
read by the sign of its cell's shrunk bias. Both sides: the "yes" side's cell and its other side.
Board singles (output/picks) are read the same way, as of their board date.

    return  flat 1 unit at SportyBet's first price;  CLV = first price x last de-vigged chance - 1
    control the same price band without the bias split (favourite-longshot is a price effect)

Writes backtest/BIAS_CHECKS_STUDY.md.  Usage: python -m backtest.bias_checks_study
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import bias_checks as bc  # noqa: E402
from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "BIAS_CHECKS_STUDY.md"
EDGE = 0.01          # |shrunk bias| above this is read as a lean


def _agg(rs: list[dict]) -> str:
    n = len(rs)
    if not n:
        return "| 0 | | |"
    rets = [x["ret"] for x in rs]
    m = sum(rets) / n
    se = math.sqrt(sum((v - m) ** 2 for v in rets) / max(n - 1, 1) / n)
    star = " **" if abs(m) > 2 * se else ""
    return f"| {n} | {sum(x['won'] for x in rs) / n:.1%} | {m:+.1%} ± {se:.1%}{star} |"


def main() -> str:
    rows = [r for r in uv.load_graded() if r.get("sport") == "football"]
    recs = bc.records(rows)
    for r in recs:
        r["ret"] = r["price"] - 1 if r["won"] else -1.0
        r["day"] = r["ko"][:10]
    days = sorted({r["day"] for r in recs})
    later = days[len(days) // 2:]
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_day[r["day"]].append(r)
    read: list[dict] = []
    tabs: dict[str, dict] = {}
    for d in later:
        tabs[d] = bc.table(recs, before=d)
        for r in by_day[d]:
            c = bc.cell(tabs[d], "football", r["key"], r["price"])
            if c:
                read.append({**r, "shrunk": c["shrunk"], "band": bc.band(r["price"])})
    L = [f"# BIAS CHECKS STUDY — {datetime.now(UTC):%Y-%m-%dT%H:%MZ}", "",
         "To-do #7 idea 2, RECORDED ONLY. Walk-forward: each day's sides are read against the "
         f"(market, price band) table of games BEFORE that day. Later half: {later[0]} .. {later[-1]}, "
         f"{len(read)} sides. Lean = |shrunk bias| > {EDGE:.0%}.", "",
         "## Every side, by the lean of its cell", "",
         "| set | n | landed | return |", "|---|---|---|---|",
         "| all " + _agg(read),
         "| cell says too long (shrunk > +1%) " + _agg([x for x in read if x["shrunk"] > EDGE]),
         "| no lean " + _agg([x for x in read if abs(x["shrunk"]) <= EDGE]),
         "| cell says too short (shrunk < -1%) " + _agg([x for x in read if x["shrunk"] < -EDGE]),
         "", "## Same split inside each price band (the control)", "",
         "| band | all | too long | too short |", "|---|---|---|---|"]
    for b in sorted({x["band"] for x in read if x["band"]}):
        inb = [x for x in read if x["band"] == b]
        cut = lambda rs: _agg(rs).strip("| ").replace(" | ", " / ")  # noqa: E731
        L.append(f"| {b} | {cut(inb)} | {cut([x for x in inb if x['shrunk'] > EDGE])} | "
                 f"{cut([x for x in inb if x['shrunk'] < -EDGE])} |")
    sg = []
    for f in sorted((ROOT / "output" / "picks").glob("picks_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        d = str(doc.get("date") or "")
        if d not in tabs:
            if d < later[0]:
                continue
            tabs[d] = bc.table(recs, before=d)
        for s in doc.get("singles") or []:
            if s.get("result") not in ("won", "lost"):
                continue
            b = bc.annotate(s, tabs[d])
            if not b or not b["yes"]:
                continue
            p = float(s["price"])
            sg.append({"won": int(s["result"] == "won"), "ret": p - 1 if s["result"] == "won" else -1.0,
                       "yes": b["yes"]["shrunk"], "no": (b["no"] or {}).get("shrunk"), "short": b["short_leg"]})
    if sg:
        L += ["", "## Board singles, as of their board date (later half)", "",
              "| set | n | landed | return |", "|---|---|---|---|",
              "| all " + _agg(sg),
              "| pick's cell too long (> +1%) " + _agg([x for x in sg if x["yes"] > EDGE]),
              "| pick's cell too short (< -1%) " + _agg([x for x in sg if x["yes"] < -EDGE]),
              "| other side's cell too long (> +1%) " + _agg([x for x in sg if (x["no"] or 0) > EDGE]),
              "| short leg (< 1.30) " + _agg([x for x in sg if x["short"]]),
              "| 1.30 and over " + _agg([x for x in sg if not x["short"]])]
    L += ["", "** = return more than 2 standard errors from zero. Nothing here changes a stake; wiring "
          "this into picks or stakes needs the Architect's OK after out-of-sample gains.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    return f"{len(read)} sides read, {len(sg)} singles"


if __name__ == "__main__":
    print(main())
