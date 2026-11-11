"""EVENT MODEL STUDY (framework #555): does engine/event_model.py predict each match stat (cards, fouls, corners,
shots, shots on target, tackles, offsides, possession...) better than the two teams' averages added together (what the
Control Room app showed before)?

Walk-forward: for every day after the first WARMUP days, the model is fitted on matches before that day only and
predicts that day's matches. Counts are scored per team with the log score and on the total with the Brier score at
the middle line; shares and expected-goals stats with the mean absolute error. The baseline gets the same treatment:
the two teams' own averages so far (Poisson for counts). A stat is published only when it beats the baseline on
every score, with at least MIN_SCORED matches behind it (EVENT_PUBLISH in the output).

    python backtest/event_study.py [stats_dir]        -> backtest/EVENT_MODEL_STUDY.md
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import event_model as em  # noqa: E402

WARMUP = 14
MIN_SCORED = 150
OUT = Path(__file__).resolve().parent / "EVENT_MODEL_STUDY.md"


def main_line(ev: str) -> float | None:
    ls = em.LINES.get(ev) or ()
    return ls[len(ls) // 2] if ls else None


def logscore(k: float, mean: float, disp: float) -> float:
    return -math.log(max(em.nb_pmf(int(round(k)), mean, disp), 1e-12))


def run(stats_dir: Path) -> dict:
    rows = em.load_history(sorted(stats_dir.glob("*.jsonl")))
    days = sorted({r["date"] for r in rows})
    start = (date.fromisoformat(days[0]) + timedelta(days=WARMUP)).isoformat()
    res: dict = defaultdict(lambda: defaultdict(float))
    fitted: dict = {}
    for r in rows:
        if r["date"] < start:
            continue
        m = fitted.get(r["date"]) or fitted.setdefault(r["date"], em.EventModel.fit(rows, before=r["date"]))
        lg = r.get("league")
        p = m.predict(lg, r["home"], r["away"])
        L = m.league(lg)
        for ev, e in p["events"].items():
            if ev not in r["stats"]:
                continue
            obs_h, obs_a = r["stats"][ev]
            bh, ba = em.baseline(rows, r["date"], lg, r["home"], r["away"], ev)
            s = res[ev]
            s["matches"] += 1
            if ev == "red":
                y = int(obs_h + obs_a > 0)
                s["br_model"] += (e["chance_any"] - y) ** 2
                s["br_base"] += (1 - math.exp(-(bh + ba)) - y) ** 2
                s["pred"] += e["chance_any"]
                s["hit"] += y
                continue
            if e["kind"] != "count":
                s["mae_model"] += abs(e["home"] - obs_h) + abs(e["away"] - obs_a)
                s["mae_base"] += abs(bh - obs_h) + abs(ba - obs_a)
                continue
            d = L.disp_team.get(ev, math.inf)
            s["ls_model"] += logscore(obs_h, e["home"], d) + logscore(obs_a, e["away"], d)
            s["ls_base"] += logscore(obs_h, max(bh, 0.05), math.inf) + logscore(obs_a, max(ba, 0.05), math.inf)
            line = main_line(ev)
            if line is not None:
                y = int(obs_h + obs_a > line)
                s["br_model"] += (e["over"][str(line)] - y) ** 2
                s["br_base"] += (em.over(line, max(bh + ba, 0.05), math.inf) - y) ** 2
    return {"rows": len(rows), "from": start, "to": days[-1], "res": {k: dict(v) for k, v in res.items()}}


def report(out: dict) -> tuple[str, list[str]]:
    lines = ["# Event model study (framework #555, record-only)", "",
             f"Walk-forward on {out['rows']} saved matches (`data/match_stats`), scored from {out['from']} to {out['to']}: "
             "each day predicted from earlier days only. Baseline = the two teams' own averages so far, which is what "
             "the app showed before. Lower is better for every score. A stat is published only when it beats the "
             f"baseline on every score with at least {MIN_SCORED} matches scored.", "",
             "| Stat | Group | Matches | Log score model / base | Brier at middle line model / base | Abs. error model / base | Publish? |",
             "|---|---|---|---|---|---|---|"]
    publish = []
    for ev in em.EVENTS:
        s = out["res"].get(ev)
        if not s:
            continue
        n = int(s["matches"])
        cells, ok = [], n >= MIN_SCORED
        if "ls_model" in s:
            a, b = s["ls_model"] / (2 * n), s["ls_base"] / (2 * n)
            cells.append(f"{a:.3f} / {b:.3f}")
            ok = ok and a < b
        else:
            cells.append("-")
        if "br_model" in s:
            a, b = s["br_model"] / n, s["br_base"] / n
            cells.append(f"{a:.4f} / {b:.4f}")
            ok = ok and a <= b
        else:
            cells.append("-")
        if "mae_model" in s:
            a, b = s["mae_model"] / (2 * n), s["mae_base"] / (2 * n)
            cells.append(f"{a:.2f} / {b:.2f}")
            ok = ok and a < b
        else:
            cells.append("-")
        lines.append(f"| {em.LABEL[ev]} | {em.GROUP[ev]} | {n} | " + " | ".join(cells) + f" | {'yes' if ok else 'no'} |")
        if ok:
            publish.append(ev)
    red = out["res"].get("red")
    if red:
        lines += ["", f"Red card: predicted {red['pred'] / red['matches']:.1%} on average, happened in "
                      f"{red['hit'] / red['matches']:.1%} of {int(red['matches'])} matches."]
    lines += ["", f"EVENT_PUBLISH = {publish}", "",
              "Notes:",
              "- The attacking stats that follow chance quality are published averaged with the framework's own "
              "expected goals (ANCHOR in `engine/event_model.py`); expected goals itself is the board's number. The "
              "walk-forward above cannot include that part (the saved stats have no pre-match model xG); the daily "
              "grading (`output/events/grades.json`) scores the published version.",
              "- Stats beyond the first 15 exist from the #556 backfill (every FotMob stat by half); until a stat has "
              f"{MIN_SCORED} scored matches it is not published.",
              "- One model form tried (attack x concede, negative binomial, shrink 6); no tuning on the scored period. "
              "Re-run every day by events.yml as the history grows.", ""]
    return "\n".join(lines), publish


def main() -> int:
    stats_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else em.STATS_DIR
    text, _ = report(run(stats_dir))
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
