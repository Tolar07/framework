"""
Football match stats predicted for today's and tomorrow's rated fixtures, and the grade of past days (framework #555).
RECORD-ONLY: writes output/events/ and nothing else; no pick, stake or board reads it.

    python monitor/events_run.py [--date YYYY-MM-DD]     (events.yml, started by the Oracle VM clock)

1. Fits engine/event_model.py on every saved match (data/match_stats).
2. For each rated fixture on the day's board (output/picks/picks_<date>.json "rated"), predicts cards, red card,
   fouls, corners, shots and shots on target, anchored to the board's own expected goals for that game.
   Writes output/events/events_<date>.json, label "shadow" (a count the study did not let through is left out).
3. Grades every events file of the last GRADE_DAYS days against the saved post-match stats and keeps a running
   record in output/events/grades.json: per event, how often the main line went the way the model leaned,
   its Brier score and the baseline's.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import event_model as em  # noqa: E402
from engine import fixture_match as fm  # noqa: E402

PICKS = ROOT / "output" / "picks"
OUT = ROOT / "output" / "events"
STUDY = ROOT / "backtest" / "EVENT_MODEL_STUDY.md"
GRADE_DAYS = 10
MAIN_LINE = {k: v[len(v) // 2] for k, v in em.LINES.items()}      # the middle line of each count


def published() -> list[str]:
    """The counts the walk-forward study let through (EVENT_PUBLISH in backtest/EVENT_MODEL_STUDY.md)."""
    try:
        m = re.search(r"EVENT_PUBLISH = \[(.*?)\]", STUDY.read_text(encoding="utf-8"))
    except OSError:
        return []
    return re.findall(r"'(\w+)'", m.group(1)) if m else []


def predict_day(day: str, model: em.EventModel, allowed: list[str]) -> dict | None:
    path = PICKS / f"picks_{day}.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    games = []
    for r in doc.get("rated") or []:
        if not (isinstance(r, dict) and r.get("home") and r.get("away")):
            continue
        xg = em.xg_from_grid(r.get("scores"))
        p = model.predict(r.get("league"), r["home"], r["away"], xg)
        p["events"] = {k: v for k, v in p["events"].items() if k in allowed}
        games.append({"home": r["home"], "away": r["away"], "league": r.get("league"),
                      "xg": [round(x, 2) for x in xg] if xg else None, **p})
    return {"date": day, "built": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "label": "shadow",
            "model": "engine/event_model.py", "study": "backtest/EVENT_MODEL_STUDY.md", "events_published": allowed,
            "games": games}


def grade(rows: list[dict], today: str) -> dict:
    """Every past events file against the saved stats of the same game (same date, both names STRONG)."""
    rec: dict = {}
    for f in sorted(OUT.glob("events_*.json")):
        day = f.stem.split("_", 1)[1]
        if day >= today:
            continue
        if (date.fromisoformat(today) - date.fromisoformat(day)).days > GRADE_DAYS:
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        played = [r for r in rows if r["date"] == day]
        for g in doc.get("games", []):
            hit = fm.find_match(g["home"], g["away"], played, lambda r: (r["home"], r["away"]))
            if not hit or not hit.strong:
                continue
            st = hit.item["stats"]
            for ev, e in g.get("events", {}).items():
                if ev not in st:
                    continue
                s = rec.setdefault(ev, {"games": 0, "lean_right": 0, "brier": 0.0, "mean_pred": 0.0, "mean_obs": 0.0,
                                        "abs_error": 0.0, "lined": 0})
                total = st[ev][0] + st[ev][1]
                s["games"] += 1
                s["mean_pred"] += e.get("total", 0.0)
                s["mean_obs"] += total
                s["abs_error"] += abs(e.get("home", 0) - st[ev][0]) + abs(e.get("away", 0) - st[ev][1])
                if ev == "red":
                    y, p = int(total > 0), e["chance_any"]
                elif ev in MAIN_LINE and str(MAIN_LINE[ev]) in e.get("over", {}):
                    line = MAIN_LINE[ev]
                    y, p = int(total > line), e["over"][str(line)]
                else:
                    continue
                s["lined"] += 1
                s["brier"] += (p - y) ** 2
                s["lean_right"] += int((p >= 0.5) == bool(y))
    for s in rec.values():
        n, nl = max(s["games"], 1), max(s["lined"], 1)
        s["brier"] = round(s["brier"] / nl, 4) if s["lined"] else None
        s["lean_right_pct"] = round(s["lean_right"] / nl, 3) if s["lined"] else None
        s["mean_pred"] = round(s["mean_pred"] / n, 2)
        s["mean_obs"] = round(s["mean_obs"] / n, 2)
        s["abs_error"] = round(s["abs_error"] / (2 * n), 2)
    return {"graded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "days": GRADE_DAYS, "events": rec}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="UK date to build (default: today and tomorrow)")
    args = ap.parse_args(argv)
    rows = em.load_history()
    if not rows:
        print("event model: no saved match stats (data/match_stats) — nothing built: NO DATA — PENDING")
        return 0
    allowed = published()
    model = em.EventModel.fit(rows)
    uk = datetime.now(ZoneInfo("Europe/London")).date()
    days = [args.date] if args.date else [uk.isoformat(), (uk + timedelta(days=1)).isoformat()]
    OUT.mkdir(parents=True, exist_ok=True)
    for day in days:
        doc = predict_day(day, model, allowed)
        if doc is None:
            print(f"{day}: no board file — nothing built")
            continue
        found = sum(1 for g in doc["games"] if all(g["teams_found"]))
        (OUT / f"events_{day}.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        print(f"{day}: {len(doc['games'])} games, both teams paired in {found}, events {allowed}")
    g = grade(rows, uk.isoformat())
    (OUT / "grades.json").write_text(json.dumps(g, indent=1) + "\n", encoding="utf-8")
    print("graded:", {k: (v["games"], v["brier"], v["abs_error"]) for k, v in g["events"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
