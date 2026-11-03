"""
REASONING RUN — the framework's thinking step over today's and tomorrow's picks files
(engine/reasoning.py), then the record of every past verdict against its result.

    python monitor/reasoning_run.py [--date YYYY-MM-DD] [--force]

A picks file is reasoned once per generated_at: a board rebuilt later is reasoned again.
It writes output/reasoning/, memory/reasoning_record.json and memory/reasoning_lessons.json, nothing else.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import reasoning as R  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV reasoning step")
    ap.add_argument("--date", action="append", help="picks date(s); default today and tomorrow (UTC)")
    ap.add_argument("--force", action="store_true", help="reason again even if this board was done")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    dates = a.date or [(now + timedelta(days=k)).date().isoformat() for k in (0, 1)]
    R.OUT_DIR.mkdir(parents=True, exist_ok=True)
    for d in dates:
        src = R.LEDGER_DIR / f"picks_{d}.json"
        if not src.exists():
            print(f"{d}: no picks file yet")
            continue
        picks = json.loads(src.read_text(encoding="utf-8"))
        out = R.OUT_DIR / f"reasoning_{d}.json"
        if out.exists() and not a.force:
            old = json.loads(out.read_text(encoding="utf-8"))
            if R.reasoned_already(old, picks, R.PROMPT):
                print(f"{d}: already reasoned for this board")
                continue
        doc = R.reason(picks, now=now)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        counts = {v: sum(1 for p in doc["picks"] if p["verdict"] == v) for v in (*R.VERDICTS, "PENDING")}
        print(f"{d}: {len(doc['picks'])} picks · model {doc['model']} · {counts}"
              + (f" · {doc['note']}" if doc["note"] else ""))
        for p in doc["picks"]:
            if p["verdict"] in ("veto", "lower"):
                print(f"  {p['verdict'].upper():5} {p['pick']} — {p['fixture']}: {p.get('reasons', '')}")
    # the NBA board too (Architect 2026-10-20: NBA treated as football is)
    for d in dates:
        src = R.LEDGER_DIR / f"nba_{d}.json"
        if not src.exists():
            continue
        board = json.loads(src.read_text(encoding="utf-8"))
        if not (board.get("picks") or board.get("picks_dropped")):
            print(f"NBA {d}: no picks")
            continue
        out = R.OUT_DIR / f"reasoning_nba_{d}.json"
        if out.exists() and not a.force:
            old = json.loads(out.read_text(encoding="utf-8"))
            if R.reasoned_already(old, board, R.PROMPT_NBA):
                print(f"NBA {d}: already reasoned for this board")
                continue
        doc = R.reason_nba(board, now=now)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"NBA {d}: {len(doc['picks'])} picks · model {doc['model']} · "
              + ", ".join(f"{p['verdict']} {p['pick']}" for p in doc["picks"])
              + (f" · {doc['note']}" if doc["note"] else ""))
    # the cognitive core grades its own past verdicts (history + post-mortem lessons) before the record
    print(f"cognitive core: {R.grade_cognitive(now=now)} newly graded")
    from engine import verdict_panel as VP     # to-do #5: the panel's out-of-sample record
    try:
        print(f"verdict panel: {VP.grade(now=now)} newly graded · {VP.summary_line()}")
    except Exception as e:  # noqa: BLE001 — never blocks the verdict record
        print(f"verdict panel: grading failed: {e}")
    try:     # step 4 (2026-11-01): champion v challenger prompt; the better Brier stays
        print(VP.prompt_round())
    except Exception as e:  # noqa: BLE001
        print(f"prompt contest failed: {e}")
    # step 2 of the bot-training plan (2026-11-01): the models fill a FACT sheet (2 of 3 must agree),
    # recorded only; the study sets each fact against the market once the picks are graded
    from engine import fact_sheet as FS
    if os.getenv("FACT_SHEET", "1") != "0":
        FS.OUT_DIR.mkdir(parents=True, exist_ok=True)
        for d in dates:
            src = R.LEDGER_DIR / f"picks_{d}.json"
            out = FS.OUT_DIR / f"facts_{d}.json"
            try:
                picks = json.loads(src.read_text(encoding="utf-8"))
                if out.exists() and not a.force and FS.done(json.loads(out.read_text(encoding="utf-8")), picks):
                    continue
                doc = FS.build(picks)
                out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
                print(f"fact sheet {d}: {doc['fields_agreed']}/{doc['fields_asked']} fields agreed · "
                      + ", ".join(f"{n} {m.get('answered', 0)}" for n, m in doc["members"].items()))
            except FileNotFoundError:
                continue
            except Exception as e:  # noqa: BLE001 — recorded only: never blocks the verdict record
                print(f"fact sheet {d}: failed: {type(e).__name__}: {e}")
        try:
            frec = FS.study()
            FS.RECORD.write_text(json.dumps(frec, indent=1), encoding="utf-8")
            print(FS.summary_line(frec))
        except Exception as e:  # noqa: BLE001
            print(f"fact sheet study failed: {e}")
    # SCOUT (Architect 2026-11-03): web/X team news, line-ups and line moves per fixture, RECORDED ONLY;
    # SCOUT_ENABLED=0 switches it off. Wrapped: it can never fail the verdict record or the save step.
    try:
        from engine import scout as SC
        for line in SC.run(dates, force=a.force):
            print(line)
        if SC.enabled():
            print(f"scout graded: {SC.grade()} new · {SC.summary_line()}")
    except Exception as e:  # noqa: BLE001
        print(f"scout failed (ignored): {type(e).__name__}: {e}")
    # step 3 (2026-11-01): one model, fitted on the graded picks, decides how much each member and
    # each fact counts; judged walk-forward against the market. Recorded only
    try:     # import inside: a missing dependency must never fail the run before its save step
        from engine import learned_weights as LW
        lw = LW.build()
        LW.RECORD.write_text(json.dumps(lw, indent=1), encoding="utf-8")
        print(LW.summary_line(lw))
    except Exception as e:  # noqa: BLE001
        print(f"learned weights failed: {e}")
    rec = R.record()
    R.RECORD.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(R.summary_line(rec))
    # once a day per sport, the reasoning rewrites its own lessons from the graded record
    # (memory/reasoning_lessons.json, read by every later run: recursive self-improvement)
    for sport in ("football", "nba"):
        les = R.reflect(sport, now=now)
        if les:
            allx = R.load_lessons()
            allx[sport] = les
            R.LESSONS.write_text(json.dumps(allx, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"lessons {sport}: {len(les['lessons'])} from {les['graded']} graded · {les['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
