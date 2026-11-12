"""
Tennis match events study (framework #559; RECORD ONLY). Writes backtest/TENNIS_EVENTS_STUDY.md and
backtest/tennis_events_fit.json (the serve level the runner reads).

Question: does the point-level serve/return model in engine/tennis_events.py, fed only the market's win chance,
beat a plain surface-adjusted average at (a) total games over/under, (b) the set score, (c) a tie-break in the match?

Data: tennis-data.co.uk ATP + WTA results 2019-2025 with Pinnacle's closing price (free; the same files as
backtest/tennis_backtest.py). The win chance fed to the model is the de-vigged Pinnacle close, and the sides are
ordered by name, never winner-first. (The Sackmann serve files the issue names are gone: 404 on 2026-11-11; aces and
double faults therefore stay PENDING, HR35.)

Walk-forward: the one free number, the chance the server wins a point between equals (`serve`), is chosen per
tour x surface on the years BEFORE the test year only (log loss of the over/under at the standard lines, 3 sets
or 5), then used on the test year. Test years: 2023, 2024, 2025. Baseline: the empirical frequencies of the past
years in the same tour x surface x best-of cell (the surface-adjusted average), which does not see the win chance.
Number of settings tried is printed (deflated-Sharpe habit). Nothing here changes a pick, stake or threshold.

  python backtest/tennis_events_study.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import tennis_events as te  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_EVENTS_STUDY.md"
FIT = ROOT / "backtest" / "tennis_events_fit.json"
GRID = (0.50, 0.52, 0.54, 0.55, 0.56, 0.57, 0.58, 0.60, 0.62, 0.64)       # serve levels tried
LINES = {3: (19.5, 20.5, 21.5, 22.5, 23.5, 24.5), 5: (30.5, 32.5, 34.5, 36.5, 38.5)}
TEST_YEARS = (2023, 2024, 2025)
MIN_TRAIN = 300           # fewer past matches in a cell than this: PENDING, no fit (HR35)
EPS = 1e-4


@lru_cache(maxsize=None)
def cell_dist(pb: int, bo: int, serve: float):
    """Model for a win chance bucketed to 2% (pb/50): (games dist, set-score dist, tie-break chance); None if out of range."""
    from engine import format_prob as fp
    d = fp.tennis_edge(pb / 50.0, bo, serve)
    if d is None:
        return None
    m = te.match_dist(d, bo, serve)
    return m["games"], m["sets"], m["tiebreak"]


def parse(rows: list[dict]) -> list[dict]:
    """Completed matches with a close price and set scores. A = the player first by name; chance = de-vigged close."""
    out = []
    for r in rows:
        if str(r.get("Comment", "Completed")).strip().lower() != "completed":
            continue
        try:
            d = float(r["Date"])
            pw, pl = float(r["PSW"]), float(r["PSL"])
            bo = int(float(r.get("Best of") or 3))
        except (KeyError, TypeError, ValueError):
            continue
        if pw <= 1 or pl <= 1 or bo not in (3, 5):
            continue
        sets = []
        for i in range(1, 6):
            try:
                sets.append((int(float(r[f"W{i}"])), int(float(r[f"L{i}"]))))
            except (KeyError, TypeError, ValueError):
                break
        if len(sets) < 2:
            continue
        w, lo = str(r.get("Winner", "")), str(r.get("Loser", ""))
        if not w or not lo or w == lo:
            continue
        a_first = w < lo
        pa = te.devig(pw, pl) if a_first else te.devig(pl, pw)
        win_sets = sum(1 for a, b in sets if a > b)
        tot = sum(a + b for a, b in sets)
        year = (datetime(1899, 12, 30) + __import__("datetime").timedelta(days=d)).year
        # score from the favourite's side (the model's A = favourite) so buckets are >= 50%
        fav_is_a_side = pa >= 0.5
        fw = win_sets if (a_first == fav_is_a_side) else len(sets) - win_sets   # favourite's sets won
        pf = pa if fav_is_a_side else 1 - pa
        out.append({"year": year, "tour": "WTA" if "WTA" in r else "ATP", "surf": str(r.get("Surface", "")),
                    "bo": bo, "p": pf, "pb": min(49, max(25, round(pf * 50))), "tot": tot,
                    "score": f"{fw}-{len(sets) - fw}", "tb": any(a + b == 13 for a, b in sets)})
    return out


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def model_over(m: dict, line: float) -> float | None:
    c = cell_dist(m["pb"], m["bo"], m["serve"])
    return None if c is None else te.over_prob(c[0], line)


def base_tables(past: list[dict]) -> dict:
    t: dict = defaultdict(lambda: {"tot": [], "score": defaultdict(int), "tb": 0, "n": 0})
    for r in past:
        c = t[(r["tour"], r["surf"], r["bo"])]
        c["tot"].append(r["tot"])
        c["score"][r["score"]] += 1
        c["tb"] += r["tb"]
        c["n"] += 1
    return t


def choose_serve(past: list[dict]) -> dict:
    """Serve level per (tour, surface) from the past only: lowest log loss of the over/under at the standard lines."""
    fit = {}
    groups: dict = defaultdict(list)
    for r in past:
        groups[(r["tour"], r["surf"])].append(r)
    for key, rows in groups.items():
        if len(rows) < MIN_TRAIN:
            continue
        best = None
        for s in GRID:
            loss = n = 0
            for r in rows:
                for ln in LINES[r["bo"]]:
                    p = model_over({**r, "serve": s}, ln)
                    if p is None:
                        continue
                    loss += ll(p, int(r["tot"] > ln))
                    n += 1
            if n and (best is None or loss / n < best[1]):
                best = (s, loss / n)
        if best:
            fit[key] = best[0]
    return fit


def evaluate(rows: list[dict]) -> dict:
    res = {"n": 0, "tried": len(GRID), "over": defaultdict(float), "over_n": 0,
           "set": defaultdict(float), "set_n": 0, "tb": defaultdict(float), "tb_n": 0,
           "cal": defaultdict(lambda: [0, 0.0, 0.0]), "years": {}, "fit": {}}
    for yr in TEST_YEARS:
        past = [r for r in rows if r["year"] < yr]
        test = [r for r in rows if r["year"] == yr]
        fit = choose_serve(past)
        res["fit"][yr] = {f"{k[0]} {k[1]}": v for k, v in sorted(fit.items())}
        base = base_tables(past)
        y_over = defaultdict(float)
        y_n = y_bets = 0
        for r in test:
            s = fit.get((r["tour"], r["surf"]))
            b = base.get((r["tour"], r["surf"], r["bo"]))
            if s is None or b is None or b["n"] < MIN_TRAIN:
                continue
            cd = cell_dist(r["pb"], r["bo"], s)
            if cd is None:
                continue
            games, sets, tbp = cd
            res["n"] += 1
            y_n += 1
            for ln in LINES[r["bo"]]:
                pm = te.over_prob(games, ln)
                pb_ = (sum(1 for t in b["tot"] if t > ln) + 1) / (len(b["tot"]) + 2)
                yv = int(r["tot"] > ln)
                res["over"]["model"] += ll(pm, yv)
                res["over"]["base"] += ll(pb_, yv)
                y_over["model"] += ll(pm, yv)
                y_over["base"] += ll(pb_, yv)
                y_bets += 1
                res["over_n"] += 1
                if ln == (22.5 if r["bo"] == 3 else 36.5):
                    k = min(9, int(pm * 10))
                    c = res["cal"][k]
                    c[0] += 1
                    c[1] += pm
                    c[2] += yv
            res["set"]["model"] += ll(sets.get(r["score"], EPS), 1)
            res["set"]["base"] += ll((b["score"].get(r["score"], 0) + 0.5) / (b["n"] + 0.5 * len(sets) + 1), 1)
            res["set_n"] += 1
            yv = int(r["tb"])
            res["tb"]["model"] += ll(tbp, yv)
            res["tb"]["base"] += ll((b["tb"] + 1) / (b["n"] + 2), yv)
            res["tb_n"] += 1
        res["years"][yr] = (y_n, y_over["model"], y_over["base"], y_bets)
    return res


def render(res: dict, now: datetime) -> str:
    n_over, n_set, n_tb = res["over_n"], res["set_n"], res["tb_n"]
    L = [f"# Tennis match events study (framework #559; record only)", "",
         f"_Generated {now:%Y-%m-%d %H:%M} UTC by backtest/tennis_events_study.py. Do not edit by hand._", "",
         "Model: engine/tennis_events.py (point -> game -> set -> match), fed the de-vigged Pinnacle close as the win",
         "chance. Baseline: the same tour x surface x best-of cell's frequencies over the earlier years (it does not see",
         "the win chance). Serve level chosen on earlier years only. Lower log loss is better.", ""]
    if not n_over:
        return "\n".join(L + ["**PENDING (HR35):** no test matches (data not loaded)."]) + "\n"
    L += [f"Test matches {res['n']:,} (2023-2025). Settings tried per cell: {res['tried']} serve levels x tour x surface "
          f"(a fit per cell, chosen on the past); the over/under lines scored: {n_over:,} line-bets.", "",
          "| What | Model log loss | Baseline log loss | Model better by |", "|---|---|---|---|"]
    verdict = {}
    for name, key, n in (("Total games over/under", "over", n_over), ("Set score", "set", n_set),
                         ("Tie-break in the match", "tb", n_tb)):
        m, b = res[key]["model"] / n, res[key]["base"] / n
        verdict[key] = m < b
        L.append(f"| {name} | {m:.4f} | {b:.4f} | {(b - m) / b:+.1%} |")
    L += ["", "By test year, total games over/under (model / baseline log loss):", ""]
    for yr, (n, m, b, nb) in sorted(res["years"].items()):
        if n:
            L.append(f"- {yr}: {n:,} matches, model {m / nb:.4f} vs baseline {b / nb:.4f}")
    L += ["", "Calibration of the model's chance of OVER 22.5 games (best of 3) / 36.5 (best of 5), by bucket:", "",
          "| Predicted bucket | Matches | Mean predicted | Actual over rate |", "|---|---|---|---|"]
    for k in sorted(res["cal"]):
        c = res["cal"][k]
        L.append(f"| {k * 10}-{k * 10 + 10}% | {c[0]:,} | {c[1] / c[0]:.1%} | {c[2] / c[0]:.1%} |")
    L += ["", "Serve level fitted per tour x surface (last test year, from earlier years only):", ""]
    last = res["fit"].get(TEST_YEARS[-1], {})
    L += [f"- {k}: {v}" for k, v in last.items()] or ["- PENDING"]
    if any(v <= GRID[0] for v in last.values()):
        L += ["", f"Warning: a fitted serve level sits on the edge of the grid ({GRID[0]}), far below a real tour serve level "
              "(ATP ~0.64, WTA ~0.57). The iid-points model squeezes the games to match the real totals by distorting the "
              "serve; read the total-games and tie-break numbers as a misfit, not a result. Next step: a per-player "
              "hold level and a favourite-side effect, once serve data exists."]
    all_ok = all(verdict.values())
    L += ["", f"**Verdict:** {'the model beats the plain average on all three events, so they stay SHADOW with the fitted serve levels' if all_ok else 'the model does NOT beat the plain average on every event: ' + ', '.join(k for k, v in verdict.items() if not v) + ' stay shadow and unproven'}. "
          "Nothing here is proven until it has also been graded against SportyBet's own price after play "
          "(monitor/tennis_events_run.py). Aces and double faults: PENDING, no free serve data (Sackmann files 404).", ""]
    return "\n".join(L)


def main() -> int:
    from backtest import tennis_totals_study as tts
    rows = parse(tts.load_results())
    res = evaluate(rows)
    now = datetime.now(UTC)
    OUT.write_text(render(res, now), encoding="utf-8", newline="\n")
    fit = res["fit"].get(TEST_YEARS[-1]) or {}
    FIT.write_text(json.dumps({"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "serve": fit,
                               "beats_baseline": {k: res[k]["model"] < res[k]["base"] for k in ("over", "set", "tb")}
                               if res["over_n"] else {}}, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.name}: {res['n']} test matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
