"""LINE-UP STUDY (2026-10-05) — run on the LIVE picks ledger, not history.

Should a team's absences change the chance itself, not only flag the pick?
No free history of team news exists, so the ledger records each pick's
missing squad-value share for both sides (field `missing`, from 2026-10-05).
This measures, for picks that depend on one side (wins, handicaps, team
goals), whether picks on a weakened side won less often than their stated
chance. Adopt an adjustment only once a bucket has 100+ graded picks and the
gap is 2+ standard deviations.
Run: python backtest/lineup_study.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.picks_ledger import LEDGER_DIR  # noqa: E402
from engine.team_news import pick_side  # noqa: E402

BUCKETS = ((0.0, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 1.01))


def main() -> None:
    rows = []
    for p in sorted(LEDGER_DIR.glob("picks_*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        for s in doc.get("singles", []):
            side = pick_side(s.get("market") or "")
            miss = (s.get("missing") or {}).get(side) if side else None
            if miss is None or s.get("result") not in ("won", "lost"):
                continue
            rows.append((miss, s["result"] == "won", float(s.get("chance_raw") or s["chance"])))
    print(f"{len(rows)} graded one-side picks with a missing-value share recorded")
    for lo, hi in BUCKETS:
        b = [r for r in rows if lo <= r[0] < hi]
        if not b:
            continue
        won = sum(w for _m, w, _c in b)
        exp = sum(c for _m, _w, c in b)
        sd = sum(c * (1 - c) for _m, _w, c in b) ** 0.5
        z = (won - exp) / sd if sd else 0.0
        print(f"  missing {lo:.0%}-{hi:.0%}: {len(b)} picks, won {won} vs {exp:.1f} expected "
              f"({(won - exp) / len(b) * 100:+.1f} pts per pick, z {z:+.1f})")


if __name__ == "__main__":
    main()
