"""
RECORDS STUDY — to-do #7 ideas 3-10, measured out of sample (recorded only, no stakes).

Every past board (output/picks/picks_<date>.json) is replayed through engine/records as of its own
date: the learned records (ensemble weight, drift CUSUM) see only boards dated before it. The later
half of the boards is read, bucket by bucket, on the graded singles: flat return at the board price,
and the board's own CLV field (closing price vs the price taken). Each idea is read on both sides
where it has two (steam vs fade, helps vs hurts, SportyBet vs Matchbook best).

Writes backtest/RECORDS_STUDY.md.  Usage: python -m backtest.records_study
"""
from __future__ import annotations

import copy
import json
import math
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import records  # noqa: E402

OUT = ROOT / "backtest" / "RECORDS_STUDY.md"


def _row(name: str, rs: list[dict]) -> str:
    n = len(rs)
    if not n:
        return f"| {name} | 0 | | | |"
    rets = [x["ret"] for x in rs]
    m = sum(rets) / n
    se = math.sqrt(sum((v - m) ** 2 for v in rets) / max(n - 1, 1) / n)
    clv = [x["clv"] for x in rs if x["clv"] is not None]
    c = f"{sum(clv) / len(clv):+.1%} ({len(clv)})" if clv else "—"
    star = " **" if abs(m) > 2 * se else ""
    return f"| {name} | {n} | {sum(x['won'] for x in rs) / n:.1%} | {m:+.1%} ± {se:.1%}{star} | {c} |"


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


BUCKETS: list[tuple[str, list[tuple[str, Callable[[dict], bool]]]]] = [
    ("3 timing", [
        ("steam (SB shortened, sharp agrees)", lambda s: s["timing"]["signal"] == "steam"),
        ("reverse line move", lambda s: s["timing"]["signal"] == "rlm"),
        ("fade (SB drifted, sharp agrees)", lambda s: s["timing"]["signal"] == "fade"),
        ("no signal", lambda s: s["timing"]["signal"] is None),
        ("board written <= 1 h before kick-off", lambda s: (s["timing"]["hours_to_ko"] or 99) <= 1),
        ("board written > 1 h before kick-off", lambda s: (s["timing"]["hours_to_ko"] or 99) > 1)]),
    ("4 context facts", [
        ("a fact hurts the pick", lambda s: any(f["direction"] < 0 for f in s["context"]["facts"])),
        ("a fact helps the pick", lambda s: any(f["direction"] > 0 for f in s["context"]["facts"])),
        ("no signed fact", lambda s: not any(f["direction"] for f in s["context"]["facts"]))]),
    ("5 exposure", [
        ("inside the league cap", lambda s: not s["exposure"]["over_cap"]),
        ("past the league cap", lambda s: s["exposure"]["over_cap"]),
        ("another single on the same match", lambda s: s["exposure"]["same_match"] > 0)]),
    ("6 shadow Kelly", [
        ("shrunk Kelly > 0", lambda s: (s["kelly"]["shrunk"] or 0) > 0),
        ("shrunk Kelly = 0", lambda s: not (s["kelly"]["shrunk"] or 0) > 0),
        ("model prefers the other side (no_edge > 0)", lambda s: (s["kelly"]["no_edge"] or 0) > 0)]),
    ("7 ensemble", [
        ("blend x price > 1", lambda s: s["blend"]["yes"] is not None and s["blend"]["yes"] * s["price"] > 1),
        ("blend x price <= 1", lambda s: s["blend"]["yes"] is not None and s["blend"]["yes"] * s["price"] <= 1),
        ("no blend (no sharp price / too few graded)", lambda s: s["blend"]["yes"] is None)]),
    ("9 drift", [
        ("family alarm: landing below its chance", lambda s: s["drift"]["alarm"] == "down"),
        ("family alarm: landing above its chance", lambda s: s["drift"]["alarm"] == "up"),
        ("no alarm", lambda s: s["drift"]["alarm"] is None)]),
    ("10 price shop", [
        ("SportyBet pays more", lambda s: (s["shop"] or {}).get("best") == "sportybet"),
        ("Matchbook pays more", lambda s: (s["shop"] or {}).get("best") == "matchbook"),
        ("SportyBet price beats the sharp chance (sb_edge > 0)", lambda s: ((s["shop"] or {}).get("sb_edge") or 0) > 0)]),
]


def main() -> str:
    files = sorted((ROOT / "output" / "picks").glob("picks_*.json"))
    dates = [f.stem[6:] for f in files if len(f.stem) == 16]
    later = set(dates[len(dates) // 2:])
    rows: list[dict] = []
    for f in files:
        d = f.stem[6:]
        if d not in later:
            continue
        try:
            doc = copy.deepcopy(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
        records.annotate_doc(doc, d)
        for s in doc.get("singles") or []:
            price = _num(s.get("price"))
            if s.get("result") not in ("won", "lost") or not price or "timing" not in s:
                continue
            s["price"] = price
            s["won"] = int(s["result"] == "won")
            s["ret"] = price - 1 if s["won"] else -1.0
            clv = _num(s.get("clv"))          # stored in percent: price / closing - 1, x100
            s["clv"] = None if clv is None else clv / 100
            rows.append(s)
    L = [f"# RECORDS STUDY — {datetime.now(UTC):%Y-%m-%dT%H:%MZ}", "",
         "To-do #7 ideas 3-10, RECORDED ONLY. Later half of the boards "
         f"({min(later) if later else '—'} .. {max(later) if later else '—'}), {len(rows)} graded singles, each "
         "board replayed through engine/records as of its own date. CLV = price taken / SportyBet closing - 1 "
         "(the board's clv field). Timing reads a board's LAST write and its sharp_p, so steam / line-up "
         "timing is measured in REASONING_IDEAS_STUDY.md (Matchbook steam) until live rows build up.", "",
         "| bucket | n | landed | return | CLV (n) |", "|---|---|---|---|---|", _row("every single", rows)]
    for idea, parts in BUCKETS:
        L.append(f"| **{idea}** | | | | |")
        for name, f in parts:
            sel = []
            for s in rows:
                try:
                    if f(s):
                        sel.append(s)
                except (KeyError, TypeError):
                    continue
            L.append(_row(name, sel))
    L += ["", "** = return more than 2 standard errors from zero. Nothing here changes a stake; wiring an "
          "idea into picks or stakes needs the Architect's OK after out-of-sample gains.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    return f"{len(rows)} singles"


if __name__ == "__main__":
    print(main())
