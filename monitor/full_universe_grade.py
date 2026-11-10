"""
FULL-UNIVERSE GRADER — every side of every SportyBet market of every finished football game, graded.
RECORD-ONLY (self-improvement #534). Reporting only: it never touches a stake, threshold, rule or the live grader.

monitor/bot_grader.py grades the legs the bots (and the board) actually bet. The model-sides study needs the
other sides too (BTTS no, under 2.5, double chance, every handicap line ...) so a rule can be judged on all the
sides it might have taken, not just the ones it took. This reads the universe archive (data/universe/graded_*),
and for each finished game settles every side of the stored ladder with the same rules the grader uses
(bot_grader.settle_on -> engine/full_markets, engine/half).

  - extra-time / penalty games (after_90) are skipped: the stored score is not the regular-time score, so the
    sides read PENDING, never guessed (HR35).
  - a side no rule knows is counted as `unknown`, never invented. A push is `void`.
  - price = the last stored price of the side (first stored if there is no last): reporting only.

    python monitor/full_universe_grade.py [--days 14] [--dry-run]

Writes data/universe/full/<kick-off day>_full.json.gz and prints the counts (no stakes, no money).
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitor import bot_grader as bg  # noqa: E402

OUT_DIR = bg.GRADED_DIR / "full"
CODE = {"won": "w", "lost": "l", "void": "v"}
MIN_ENTRIES, MAX_UNKNOWN = 2000, 0.10     # the issue's reject bars


def _ladder(g: dict) -> dict:
    last = ((g.get("last") or {}).get("p") or {}).get("ladder") or {}
    first = ((g.get("first") or {}).get("p") or {}).get("ladder") or {}
    return {**first, **last}


def grade_game(g: dict) -> tuple[dict | None, Counter]:
    """One finished football game -> {'sides': {key: [price, w|l|v]}, ...}; None when it cannot be graded."""
    c: Counter = Counter()
    r = g.get("result") or {}
    if g.get("sport") != "football" or r.get("h") is None or r.get("a") is None:
        return None, c
    if r.get("after_90"):
        c["pending_extra_time"] += 1
        return None, c
    sides = {}
    for key, price in _ladder(g).items():
        res = bg.settle_on(key, int(r["h"]), int(r["a"]), r.get("ht"))
        if res not in CODE:
            c["unknown"] += 1
            continue
        sides[key] = [price, CODE[res]]
        c[res] += 1
    if not sides:
        return None, c
    return {"id": g["id"], "home": g.get("home"), "away": g.get("away"), "comp": g.get("comp"),
            "ko": g.get("ko"), "score": [r["h"], r["a"]], "sides": sides}, c


def run(since: str, folder: Path | None = None, out_dir: Path | None = None, dry: bool = False) -> dict:
    games = bg.Games(since, folder=folder)
    by_day: dict[str, list[dict]] = defaultdict(list)
    tally: Counter = Counter()
    for g in games.by_id.values():
        if (g.get("ko") or "")[:10] < since:
            continue
        doc, c = grade_game(g)
        tally.update(c)
        if doc:
            by_day[doc["ko"][:10]].append(doc)
            tally["games"] += 1
    total = tally["won"] + tally["lost"] + tally["void"]
    seen = total + tally["unknown"]
    summary = {"since": since, "games": tally["games"], "entries": total, "won": tally["won"],
               "lost": tally["lost"], "void": tally["void"], "unknown": tally["unknown"],
               "unknown_rate": round(tally["unknown"] / seen, 4) if seen else None,
               "pending_extra_time_games": tally["pending_extra_time"],
               "reject": bool(total < MIN_ENTRIES or (seen and tally["unknown"] / seen > MAX_UNKNOWN))}
    if not dry:
        out = out_dir or OUT_DIR
        out.mkdir(parents=True, exist_ok=True)
        for day, docs in by_day.items():
            with gzip.open(out / f"{day}_full.json.gz", "wt", encoding="utf-8") as f:
                json.dump({"day": day, "games": sorted(docs, key=lambda d: d["id"])}, f, separators=(",", ":"))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    since = (datetime.now(UTC) - timedelta(days=a.days)).date().isoformat()
    print(json.dumps(run(since, dry=a.dry_run)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
