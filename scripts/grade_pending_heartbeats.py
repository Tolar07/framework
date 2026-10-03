"""Grade PENDING heartbeats against real match scores.

WHY THIS EXISTS
`process_heartbeat_result()` in engine/heartbeat_lineage.py has zero callers —
nothing in the pipeline or the schedule ever grades a heartbeat. So every
heartbeat produced since the lineage model went in sits at PENDING, the
lineages all read 0W/0L despite being generation 3, and the survival model
(WIN -> two offspring, LOSS -> extinction) has never actually run.

The standalone verifier could not close the gap either: it graded off the
`pick` DISPLAY STRING and reported "not machine-gradable" for
"Under 3.5 goals" and every double chance. The record's `market_type` is a
coarse bucket for choosing a display arrow ("O/U" carries neither the line nor
the side) and is wrong for Draw No Bet. output/heartbeat.py now persists the
canonical `market_key`; records written before that carry only the display
string, so this recovers the key by parsing it.

The parse is DETERMINISTIC, not a guess: those display strings are generated
from the keys by markets.display(), so the mapping back is exact. Anything
this cannot resolve is reported UNGRADABLE and left PENDING (HR35) — never
assumed, and never defaulted to a result.

Usage:
    python scripts/grade_pending_heartbeats.py            # report only
    python scripts/grade_pending_heartbeats.py --apply    # write results
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.espn_results import fetch_results_for_date  # noqa: E402
from verification.fixture_matcher import names_match, normalize_team_name  # noqa: E402

HISTORY = Path(__file__).resolve().parent.parent / "data" / "heartbeat" / "history.jsonl"


def market_key_from_pick(pick: str, home: str, away: str) -> str | None:
    """Recover the canonical market key from a rendered pick label."""
    if not pick:
        return None
    p = pick.strip()
    low = p.lower()

    m = re.match(r"^(over|under)\s+([\d.]+)\s+goals?$", low)
    if m:
        side, line = m.group(1).upper(), m.group(2).replace(".", "_")
        return f"{side}_{line}"

    if low.startswith("both teams to score"):
        return "BTTS_NO" if low.rstrip().endswith("no") else "BTTS_YES"

    if "draw no bet" in low:
        team = p[: low.index("draw no bet")].strip()
        if names_match(normalize_team_name(team), normalize_team_name(home)):
            return "DNB_HOME"
        if names_match(normalize_team_name(team), normalize_team_name(away)):
            return "DNB_AWAY"
        return None

    if "double chance" in low or " or " in low:
        body = re.sub(r"\s*\(double chance\)\s*$", "", p, flags=re.I).strip()
        parts = [x.strip() for x in re.split(r"\s+or\s+", body, flags=re.I)]
        if len(parts) != 2:
            return None
        def side(tok: str) -> str | None:
            if tok.lower() == "draw":
                return "X"
            if names_match(normalize_team_name(tok), normalize_team_name(home)):
                return "1"
            if names_match(normalize_team_name(tok), normalize_team_name(away)):
                return "2"
            return None
        a, b = side(parts[0]), side(parts[1])
        if not a or not b:
            return None
        combo = "".join(sorted(a + b, key="1X2".index))  # canonical 1-X-2 order
        return {"1X": "DC_1X", "12": "DC_12", "X2": "DC_X2"}.get(combo)

    if low.endswith("to win"):
        team = p[: -len("to win")].strip()
        if names_match(normalize_team_name(team), normalize_team_name(home)):
            return "1X2_HOME"
        if names_match(normalize_team_name(team), normalize_team_name(away)):
            return "1X2_AWAY"
        return None
    if low == "draw":
        return "1X2_DRAW"
    return None


def grade(market_key: str, hg: int, ag: int) -> str | None:
    """WIN/LOSS for a settled score, or None when the market pushes."""
    total = hg + ag
    if market_key.startswith(("OVER_", "UNDER_")):
        side, _, line_s = market_key.partition("_")
        line = float(line_s.replace("_", "."))
        if total == line:
            return None  # whole-number line pushes
        over = total > line
        return "WIN" if (over if side == "OVER" else not over) else "LOSS"
    if market_key == "BTTS_YES":
        return "WIN" if hg > 0 and ag > 0 else "LOSS"
    if market_key == "BTTS_NO":
        return "WIN" if hg == 0 or ag == 0 else "LOSS"
    if market_key == "1X2_HOME":
        return "WIN" if hg > ag else "LOSS"
    if market_key == "1X2_AWAY":
        return "WIN" if ag > hg else "LOSS"
    if market_key == "1X2_DRAW":
        return "WIN" if hg == ag else "LOSS"
    if market_key == "DNB_HOME":
        return None if hg == ag else ("WIN" if hg > ag else "LOSS")
    if market_key == "DNB_AWAY":
        return None if hg == ag else ("WIN" if ag > hg else "LOSS")
    if market_key == "DC_1X":
        return "WIN" if hg >= ag else "LOSS"
    if market_key == "DC_X2":
        return "WIN" if ag >= hg else "LOSS"
    if market_key == "DC_12":
        return "WIN" if hg != ag else "LOSS"
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write results back")
    args = ap.parse_args()

    rows = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]
    pending = [r for r in rows if r.get("result") == "PENDING"]
    print(f"G| {len(pending)} PENDING of {len(rows)} records")

    by_date: dict[str, list] = {}
    for r in pending:
        by_date.setdefault(r["date"], []).append(r)

    graded, ungradable = {}, []
    for day, recs in sorted(by_date.items()):
        try:
            results = fetch_results_for_date(day)
        except Exception as e:
            print(f"G| {day}: results fetch FAILED ({str(e)[:60]}) — left PENDING")
            continue
        print(f"\nG| {day}: {len(results)} completed matches fetched")
        for r in recs:
            fx = r.get("fixture") or ""
            if " v " not in fx:
                ungradable.append((r, "fixture not parseable"))
                continue
            home, away = [x.strip() for x in fx.split(" v ", 1)]
            hit = None
            for m in results:
                if (names_match(normalize_team_name(m.home_team), normalize_team_name(home))
                        and names_match(normalize_team_name(m.away_team), normalize_team_name(away))):
                    hit = m
                    break
            if hit is None:
                ungradable.append((r, "no result found"))
                print(f"G|   {fx[:38]:40} UNGRADABLE — no result found")
                continue
            key = r.get("market_key") or market_key_from_pick(r.get("pick") or "", home, away)
            if not key:
                ungradable.append((r, f"cannot resolve market from {r.get('pick')!r}"))
                print(f"G|   {fx[:38]:40} UNGRADABLE — market {r.get('pick')!r}")
                continue
            hg, ag = hit.home_score, hit.away_score
            res = grade(key, hg, ag)
            if res is None:
                ungradable.append((r, f"{key} pushes on {hg}-{ag}"))
                print(f"G|   {fx[:38]:40} PUSH ({key}, {hg}-{ag})")
                continue
            graded[(r["date"], r["lineage_id"])] = (res, key, f"{hg}-{ag}")
            print(f"G|   {fx[:38]:40} {res:4} — {key} on {hg}-{ag}")

    print(f"\nG| graded {len(graded)}, ungradable {len(ungradable)}")
    for r, why in ungradable:
        print(f"G|   still PENDING: {r['date']} {r['lineage_id']} — {why}")

    if not args.apply:
        print("\nG| report only; re-run with --apply to write results")
        return 0

    n = 0
    for r in rows:
        k = (r.get("date"), r.get("lineage_id"))
        if r.get("result") == "PENDING" and k in graded:
            res, key, score = graded[k]
            r["result"] = res
            r["market_key"] = key
            r["settled_score"] = score
            r["graded_by"] = "scripts/grade_pending_heartbeats.py"
            n += 1
    HISTORY.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
    print(f"G| wrote {n} results to {HISTORY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
