"""EVENT MODEL STUDY (framework #555): does engine/event_model.py predict cards, fouls, corners, shots and shots on
target better than the two teams' season averages added together (what the Control Room app showed before)?

Walk-forward: for every day after the first WARMUP days, the model is fitted on matches before that day only and
predicts that day's matches. Scored per team count with the log score (lower is better), and on the totals with the
Brier score at the usual SportyBet lines. The baseline gets the same treatment: the two teams' own averages so far,
as Poisson means. A count the model does not beat is not published (EVENT_PUBLISH in the output says which).

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
OUT = Path(__file__).resolve().parent / "EVENT_MODEL_STUDY.md"
MAIN_LINE = {"yellow": 4.5, "fouls": 22.5, "corners": 9.5, "shots": 23.5, "sot": 8.5}


def logscore(k: int, mean: float, disp: float) -> float:
    return -math.log(max(em.nb_pmf(int(k), mean, disp), 1e-12))


def run(stats_dir: Path) -> dict:
    rows = em.load_history(sorted(stats_dir.glob("*.jsonl")))
    days = sorted({r["date"] for r in rows})
    start = (date.fromisoformat(days[0]) + timedelta(days=WARMUP)).isoformat()
    res = defaultdict(lambda: {"n": 0, "ls_model": 0.0, "ls_base": 0.0, "br_model": 0.0, "br_base": 0.0, "nt": 0,
                               "red_n": 0, "red_hit": 0, "red_p": 0.0})
    fitted = {}
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
            if ev == "red":
                s["red_n"] += 1
                s["red_hit"] += int(obs_h + obs_a > 0)
                s["red_p"] += e["chance_any"]
                pb = 1 - math.exp(-(bh + ba))
                y = int(obs_h + obs_a > 0)
                s["br_model"] += (e["chance_any"] - y) ** 2
                s["br_base"] += (pb - y) ** 2
                s["nt"] += 1
                continue
            d = L.disp_team.get(ev, math.inf)
            s["ls_model"] += logscore(obs_h, e["home"], d) + logscore(obs_a, e["away"], d)
            s["ls_base"] += logscore(obs_h, max(bh, 0.05), math.inf) + logscore(obs_a, max(ba, 0.05), math.inf)
            s["n"] += 2
            line = MAIN_LINE[ev]
            y = int(obs_h + obs_a > line)
            pm = e["over"][str(line)]
            pb = em.over(line, max(bh + ba, 0.05), math.inf)
            s["br_model"] += (pm - y) ** 2
            s["br_base"] += (pb - y) ** 2
            s["nt"] += 1
    return {"rows": len(rows), "from": start, "to": days[-1], "res": dict(res)}


def report(out: dict) -> str:
    lines = ["# Event model study (framework #555, record-only)", "",
             f"Walk-forward on {out['rows']} saved matches (`data/match_stats`), scored from {out['from']} to {out['to']}: "
             "each day predicted from earlier days only. Baseline = the two teams' own averages so far (Poisson), "
             "which is what the app showed before. Lower is better for both scores.", "",
             "| Event | Team counts scored | Log score: model | Log score: baseline | Totals scored | Brier at the main line: model | Brier: baseline | Publish? |",
             "|---|---|---|---|---|---|---|---|"]
    publish = []
    for ev in ("yellow", "fouls", "corners", "shots", "sot", "red"):
        s = out["res"].get(ev)
        if not s:
            continue
        if ev == "red":
            bm, bb = s["br_model"] / max(s["nt"], 1), s["br_base"] / max(s["nt"], 1)
            ok = bm < bb
            lines.append(f"| Red card (any) | - | - | - | {s['nt']} | {bm:.4f} | {bb:.4f} | {'yes' if ok else 'no'} |")
            lines.append("")
            lines.append(f"Red card: predicted {s['red_p'] / max(s['red_n'], 1):.1%} on average, happened in "
                         f"{s['red_hit'] / max(s['red_n'], 1):.1%} of {s['red_n']} matches.")
        else:
            lm, lb = s["ls_model"] / max(s["n"], 1), s["ls_base"] / max(s["n"], 1)
            bm, bb = s["br_model"] / max(s["nt"], 1), s["br_base"] / max(s["nt"], 1)
            ok = lm < lb and bm <= bb
            lines.append(f"| {em.LABEL[ev]} (line {MAIN_LINE[ev]}) | {s['n']} | {lm:.4f} | {lb:.4f} | {s['nt']} | {bm:.4f} | {bb:.4f} | {'yes' if ok else 'no'} |")
        if ok:
            publish.append(ev)
    lines += ["", f"EVENT_PUBLISH = {publish}", "",
              "Notes:",
              "- Shots and shots on target are published anchored to the framework's own expected goals (ANCHOR in "
              "`engine/event_model.py`). The walk-forward above cannot include that part: the saved stats have no "
              "pre-match model xG. The daily grading (`output/events/grades.json`) scores the anchored version.",
              "- Five weeks of history (October-November 2026); teams have 3-6 matches each, so team rates are heavily "
              "shrunk to the league. The comparison will be re-run as the history grows.",
              "- Tried: one model form (attack x concede, negative binomial, shrink 6). No tuning on the scored period.", ""]
    return "\n".join(lines), publish


def main() -> int:
    stats_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else em.STATS_DIR
    text, publish = report(run(stats_dir))
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
