"""
Tennis match events: daily runner + grading (framework #559). RECORD-ONLY / SHADOW.

For every singles tennis match on the multi-sport board (output/multisport/tennis/ms_<day>.json) writes the point-level
model's numbers (set scores, total games over/under at SportyBet's own lines, tie-break) to output/tennis_events/
<day>.json, labelled `shadow`. Each past day is graded once from the board's own recorded result (set scores) and kept in
output/tennis_events/grades.json (standing order 53). Picks nothing, stakes nothing. Aces / double faults: PENDING.

  python monitor/tennis_events_run.py [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import tennis_events as te  # noqa: E402

BOARD = ROOT / "output" / "multisport" / "tennis"
OUT = ROOT / "output" / "tennis_events"
FIT = ROOT / "backtest" / "tennis_events_fit.json"
GRADE_DAYS = 14


def study() -> tuple[dict, dict]:
    """(serve level per tour, which events beat the plain average in the study). Missing study = defaults, nothing proven."""
    try:
        doc = json.loads(FIT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    by_tour: dict[str, list[float]] = {}
    for k, v in (doc.get("serve") or {}).items():
        by_tour.setdefault(k.split()[0], []).append(v)
    return {t: round(sum(v) / len(v), 3) for t, v in by_tour.items()}, doc.get("beats_baseline") or {}


def build_day(day: str, serve: dict, beats: dict) -> dict | None:
    f = BOARD / f"ms_{day}.json"
    if not f.exists():
        return None
    board = json.loads(f.read_text(encoding="utf-8"))
    games = []
    for gid, g in sorted((board.get("games") or {}).items()):
        sides = g.get("sides") or {}
        p = te.home_chance(sides)
        pred = te.predict(p, g.get("comp") or "", tuple(te.total_lines(sides)) or te.LINES_DEFAULT, serve,
                          g.get("home") or "")
        games.append({"id": gid, "comp": g.get("comp"), "home": g.get("home"), "away": g.get("away"), "ko": g.get("ko"),
                      "board_home_chance": None if p is None else round(p, 4),
                      "model": pred, "why": None if pred else "PENDING: no two-way price, or doubles (not modelled)"})
    return {"date": day, "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "label": "shadow",
            "study_beats_plain_average": beats, "games": games}


def _ll(p: float, y: int) -> float:
    p = min(1 - 1e-4, max(1e-4, p))
    return -math.log(p if y else 1 - p)


def grade_day(day: str, doc: dict) -> dict | None:
    f = BOARD / f"ms_{day}.json"
    if not f.exists():
        return None
    board = json.loads(f.read_text(encoding="utf-8")).get("games") or {}
    agg = {"matches": 0, "over_n": 0, "over_ll": 0.0, "set_n": 0, "set_ll": 0.0, "tb_n": 0, "tb_ll": 0.0, "win_ll": 0.0}
    for g in doc.get("games") or []:
        m = g.get("model")
        res = (board.get(g["id"]) or {}).get("result")
        got = te.games_from_periods((res or {}).get("periods"))
        if not m or not got or not res.get("winner"):
            continue
        tot, n_sets, tb = got
        per = res["periods"]
        hs = sum(1 for a, b in per if a > b)
        agg["matches"] += 1
        agg["win_ll"] += _ll(m["win_home"], int(res["winner"] == 1))
        for ln, po in m["over"].items():
            if float(ln) in te.total_lines((board.get(g["id"]) or {}).get("sides") or {}):
                agg["over_n"] += 1
                agg["over_ll"] += _ll(po, int(tot > float(ln)))
        agg["set_n"] += 1
        agg["set_ll"] += _ll(m["set_scores"].get(f"{hs}-{n_sets - hs}", 0.0), 1)
        agg["tb_n"] += 1
        agg["tb_ll"] += _ll(m["tiebreak"], int(tb))
    return agg if agg["matches"] else None


def grade_files(today: date) -> dict:
    path = OUT / "grades.json"
    rec = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"days": {}}
    for f in sorted(OUT.glob("20*.json"))[-GRADE_DAYS:]:
        day = f.stem
        if day >= today.isoformat() or day in rec["days"]:
            continue
        a = grade_day(day, json.loads(f.read_text(encoding="utf-8")))
        if a:
            rec["days"][day] = a
    tot = {k: sum(d[k] for d in rec["days"].values()) for k in ("matches", "over_n", "over_ll", "set_n", "set_ll", "tb_n", "tb_ll")}
    rec["total"] = {**tot, "over_logloss": tot["over_ll"] / tot["over_n"] if tot["over_n"] else None,
                    "set_logloss": tot["set_ll"] / tot["set_n"] if tot["set_n"] else None,
                    "tb_logloss": tot["tb_ll"] / tot["tb_n"] if tot["tb_n"] else None}
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8", newline="\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    a = ap.parse_args()
    now = datetime.now(UTC)
    day = date.fromisoformat(a.date) if a.date else now.date()
    serve, beats = study()
    OUT.mkdir(parents=True, exist_ok=True)
    for d in (day, day + timedelta(days=1)):
        doc = build_day(d.isoformat(), serve, beats)
        if doc is None:
            print(f"  {d}: PENDING, no tennis board file")
            continue
        (OUT / f"{d.isoformat()}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
        print(f"  {d}: {sum(1 for g in doc['games'] if g['model'])}/{len(doc['games'])} matches modelled")
    rec = grade_files(day)
    print(f"  graded days: {len(rec['days'])}, matches: {rec['total']['matches']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
