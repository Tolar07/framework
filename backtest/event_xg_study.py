"""EVENT MODEL, GAME-STATE STUDY (framework #566): does tying every match stat to the goals model's expected game
(xG gap, total xG, draw chance) predict the stat better than the current event model? RECORD-ONLY SHADOW.

Today only the attacking stats follow the board's xG (engine/event_model.py FOLLOWS_XG, ANCHOR). Cards, fouls, corners,
possession, passes and defensive stats come from team rates alone. Candidate: for each stat, a log-linear correction
on the current model's mean for one side,

    mean_side = current_mean_side * exp(b0 + b1 * (own xG - opponent xG) + b2 * (total xG - 2.7) + b3 * (draw chance - 0.27))

fitted by ridge Poisson regression on earlier matches only (walk-forward, pooled over leagues: about 1,000 matches
are too few to fit per league group; the league is already in the current mean). The current model stays the
baseline; a stat is marked TIED only when the tied version beats it on both the log score and the Brier score at the
middle line, with at least MIN_SCORED matches behind it. Nothing here changes any price, pick, stake or published number.

Pre-match xG of past matches: output/picks/picks_<date>.json `rated` fixtures carry the board's 0-5 score table
(`scores`); it is paired with data/match_stats lines of the same day and the same league, both team names the same or
STRONG by engine/fixture_match. A match with no pairing is not scored (PENDING, never invented).

    python backtest/event_xg_study.py      -> backtest/EVENT_XG_STUDY.md
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import event_model as em  # noqa: E402
from engine import fixture_match as fm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PICKS = ROOT / "output" / "picks"
OUT = Path(__file__).resolve().parent / "EVENT_XG_STUDY.md"
WARMUP_PAIRS = 80       # paired matches needed before the correction is fitted at all
MIN_SCORED = 150
RIDGE = 8.0
MEAN_TOTAL_XG, MEAN_DRAW = 2.7, 0.27
FEATURES = ("own-minus-opp xG", "total xG", "draw chance")


def _same(a: str, b: str) -> bool:
    return a == b or fm.team_score(a, b) >= fm.STRONG


def pair_xg(rows: list[dict], picks_dir: Path = PICKS) -> dict[int, tuple[tuple[float, float], float]]:
    """index in `rows` -> ((xg_home, xg_away), draw chance) from that day's rated fixtures."""
    by_day: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(picks_dir.glob("picks_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for r in doc.get("rated") or []:
            if isinstance(r, dict) and r.get("scores") and r.get("home") and r.get("away") and r.get("p"):
                by_day[str(r.get("kickoff") or doc.get("date"))[:10]].append(r)
    out = {}
    for i, row in enumerate(rows):
        for r in by_day.get(row["date"], ()):
            if r.get("league") == row.get("league") and _same(r["home"], row["home"]) and _same(r["away"], row["away"]):
                xg = em.xg_from_grid(r["scores"])
                if xg:
                    out[i] = (xg, float(r["p"][1]))
                break
    return out


def feats(own: float, opp: float, draw: float) -> list[float]:
    return [1.0, own - opp, own + opp - MEAN_TOTAL_XG, draw - MEAN_DRAW]


def fit_tie(samples: list[tuple[list[float], float, float]]) -> np.ndarray | None:
    """Ridge Poisson regression of observed count on features with offset log(current mean). None if too few."""
    if len(samples) < 2 * WARMUP_PAIRS:
        return None
    X = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    off = np.log(np.maximum([s[2] for s in samples], 0.05))
    b = np.zeros(X.shape[1])
    pen = np.diag([0.0] + [RIDGE] * (X.shape[1] - 1))
    for _ in range(25):
        mu = np.exp(np.clip(off + X @ b, -6, 12))
        g = X.T @ (y - mu) - pen @ b
        H = X.T @ (X * mu[:, None]) + pen + 1e-9 * np.eye(len(b))
        step = np.clip(np.linalg.solve(H, g), -0.5, 0.5)
        b = np.clip(b + step, -2.0, 2.0)
        if np.max(np.abs(step)) < 1e-7:
            break
    return b


def tied_mean(mean: float, own: float, opp: float, draw: float, b: np.ndarray | None) -> float:
    if b is None:
        return mean
    return mean * math.exp(float(np.dot(b, feats(own, opp, draw))))


def run(stats_dir: Path = em.STATS_DIR, picks_dir: Path = PICKS) -> dict:
    rows = em.load_history(sorted(stats_dir.glob("*.jsonl")))
    paired = pair_xg(rows, picks_dir)
    days = sorted({rows[i]["date"] for i in paired})
    recs: dict[str, list[dict]] = defaultdict(list)     # stat -> chronological per-match records
    for d in days:
        m = em.EventModel.fit(rows, before=d)
        for i in (j for j in paired if rows[j]["date"] == d):
            r = rows[i]
            (xh, xa), draw = paired[i]
            p = m.predict(r.get("league"), r["home"], r["away"], (xh, xa))
            L = m.league(r.get("league"))
            for ev, e in p["events"].items():
                if e["kind"] != "count" or ev not in r["stats"]:
                    continue
                recs[ev].append({"date": d, "xg": (xh, xa), "draw": draw, "mean": (e["home"], e["away"]),
                                 "obs": tuple(r["stats"][ev]), "disp": L.disp_team.get(ev, math.inf),
                                 "dtot": L.disp_total.get(ev, math.inf)})
    res: dict = {}
    for ev, rs in recs.items():
        s = defaultdict(float)
        coefs = None
        for k, r in enumerate(rs):
            if k == 0 or rs[k - 1]["date"] != r["date"]:          # refit once per day on earlier days only
                prior = rs[:k]
                samples = []
                for x in prior:
                    (xh, xa), dr = x["xg"], x["draw"]
                    samples.append((feats(xh, xa, dr), x["obs"][0], x["mean"][0]))
                    samples.append((feats(xa, xh, dr), x["obs"][1], x["mean"][1]))
                coefs = fit_tie(samples)
            if coefs is None:
                continue
            (xh, xa), dr = r["xg"], r["draw"]
            th, ta = tied_mean(r["mean"][0], xh, xa, dr, coefs), tied_mean(r["mean"][1], xa, xh, dr, coefs)
            ch, ca = r["mean"]
            oh, oa = r["obs"]
            s["n"] += 1
            s["ls_cur"] += em_ls(oh, ch, r["disp"]) + em_ls(oa, ca, r["disp"])
            s["ls_tie"] += em_ls(oh, th, r["disp"]) + em_ls(oa, ta, r["disp"])
            lines = em.LINES.get(ev) or ()
            if lines:
                ln = lines[len(lines) // 2]
                y = int(oh + oa > ln)
                s["br_cur"] += (em.over(ln, ch + ca, r["dtot"]) - y) ** 2
                s["br_tie"] += (em.over(ln, th + ta, r["dtot"]) - y) ** 2
        if s["n"]:
            res[ev] = {**s, "coefs": [round(float(c), 4) for c in coefs] if coefs is not None else None}
    return {"rows": len(rows), "paired": len(paired), "res": res,
            "from": days[0] if days else "PENDING", "to": days[-1] if days else "PENDING"}


def em_ls(k: float, mean: float, disp: float) -> float:
    return -math.log(max(em.nb_pmf(int(round(k)), max(mean, 0.05), disp), 1e-12))


def report(out: dict) -> tuple[str, list[str]]:
    lines = ["# Event model, game-state study (framework #566, record-only shadow)", "",
             f"{out['paired']} of {out['rows']} saved matches have the board's pre-match xG "
             f"(rated fixtures paired by day, league and team names); scored walk-forward from the first day the "
             f"correction could be fitted ({WARMUP_PAIRS} matches, i.e. 2x that many team-sides) to {out['to']}. "
             "Current = engine/event_model.py as published. Tied = the same mean times a fitted "
             "exp(b0 + b1*own-minus-opp xG + b2*total xG + b3*draw chance). Lower is better. A stat is TIED "
             f"only when it wins on the log score and the Brier score at the middle line with {MIN_SCORED}+ matches.", "",
             "| Stat | Matches | Log score tied / current | Brier tied / current | Last fit b0, xG gap, total xG, draw | TIED? |",
             "|---|---|---|---|---|---|"]
    tied = []
    for ev in em.EVENTS:
        s = out["res"].get(ev)
        if not s:
            continue
        n = int(s["n"])
        a, b = s["ls_tie"] / (2 * n), s["ls_cur"] / (2 * n)
        ok = n >= MIN_SCORED and a < b
        if "br_cur" in s:
            ba, bb = s["br_tie"] / n, s["br_cur"] / n
            ok = ok and ba <= bb
            br = f"{ba:.4f} / {bb:.4f}"
        else:
            br = "-"
        lines.append(f"| {em.LABEL[ev]} | {n} | {a:.4f} / {b:.4f} | {br} | {s['coefs']} | {'yes' if ok else 'no'} |")
        if ok:
            tied.append(ev)
    if not out["res"]:
        lines.append("| PENDING | 0 | - | - | - | no |")
    lines += ["", f"EVENT_TIED = {tied}", "",
              "If this list stays empty the idea is rejected (#566: reject if no stat improves). A stat on the "
              "list is only a candidate: switching `engine/event_model.py` to the tied mean is a separate change "
              "that needs the Architect's normal promotion gate. Counts only (the red-card count is scored as a count, "
              "not as the chance of any red); possession and the expected-goals stats are not scored here.", ""]
    return "\n".join(lines), tied


def main() -> int:
    text, _ = report(run())
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
