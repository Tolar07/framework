"""
Nightly match study (match_study.yml; Architect 2026-10-26: "the framework
needs to study each match. The ones that we bet and the one that we do not
bet").

1. data/match_study.collect()  — every newly finished match of the covered
   competitions, read from FotMob (formation, shot map, press, line, state).
2. engine/tactics.build_profiles — every team's tactical profile, updated
   with the match it just played -> data/tactics/profiles.json (the board
   reads it at 21:47 and 06:47).
3. Walk-forward replay (engine/tactics_study) from WF_START: each match read
   from the profiles as they stood before it. New matches are explained
   (expected v happened v why) into memory/match_study_log.jsonl.
4. Lessons tested on the matches they hadn't seen -> memory/tactics_lessons.json;
   the weight against SportyBet's price refitted -> data/tactics/calibration.json;
   backtest/TACTICS_STUDY.md.

    python monitor/match_study_run.py [--no-fetch]
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import match_study as ms  # noqa: E402
from engine import tactics as tx  # noqa: E402
from engine import tactics_study as ts  # noqa: E402

WF_START = "2026-09-01"            # first week the replay reads (profiles need ~3 games a team)
FIRST_LESSONS_AT = "2026-10-01"    # the first candidates were written from matches before this day


def logged_ids(path: Path = ts.STUDY_LOG) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(x)["fotmob_id"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}


def main(fetch: bool = True) -> int:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if fetch:
        n, notes = ms.collect()
        print(f"match study: {n} new match(es) read")
        for x in notes:
            print("  ", x)
    rows = ms.load()
    if not rows:
        print("match study: NO DATA — PENDING (nothing studied yet)")
        return 0
    db = tx.build_profiles(rows)
    tx.save(db)
    print(f"tactical profiles: {len(db['teams'])} team(s) from {len(rows)} match(es)")

    base = ts.walk_forward(rows, WF_START, effects={})
    lessons = tx.load_lessons()
    if not lessons.get("lessons"):          # first run: write candidates as they stood on FIRST_LESSONS_AT
        lessons = ts.update_lessons(base, FIRST_LESSONS_AT, lessons)
    lessons = ts.update_lessons(base, today, lessons)
    tx.LESSONS.parent.mkdir(parents=True, exist_ok=True)
    tx.LESSONS.write_text(json.dumps(lessons, indent=1, ensure_ascii=False), encoding="utf-8")
    eff = tx.proven_effects(lessons)
    print(f"lessons: {sum(x['status'] == 'candidate' for x in lessons['lessons'].values())} candidate(s), "
          f"{len(eff)} proven")

    preds = ts.walk_forward(rows, WF_START, effects=eff) if eff else base
    made = ts.attach_prices(preds, ts.universe_prices())
    weight = ts.fit_weight(preds)
    weight.update({"fitted_at": today, "priced_pairs": made})
    tx.CALIB.parent.mkdir(parents=True, exist_ok=True)
    tx.CALIB.write_text(json.dumps(weight, indent=1), encoding="utf-8")
    print(f"weight: {weight}")

    done = logged_ids()
    new = [ts.explain(p) for p in preds if str(p["row"]["fotmob_id"]) not in done]
    ts.STUDY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ts.STUDY_LOG.open("a", encoding="utf-8") as f:
        for e in new:
            f.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"studied: {len(new)} match(es) explained")
    try:   # the why record: graded picks set against the matches just studied
        from engine import why_record
        print(f"why record: {len(why_record.build())} graded single(s) classed")
    except Exception as e:  # noqa: BLE001
        print(f"why record skipped ({e})")
    ts.report(preds, weight, lessons)
    return 0


if __name__ == "__main__":
    sys.exit(main(fetch="--no-fetch" not in sys.argv))
