"""
Baseball events study (framework #587, Event models #8; RECORD ONLY). Writes backtest/BASEBALL_EVENTS_STUDY.md.

Question: does the model in engine/baseball_events.py (team run ratings -> nine-inning means -> the MLB's own inning
shares) beat the plain two-teams' season-average baseline at (a) runs in the first five innings (over 3.5 / 4.5 / 5.5,
both teams), (b) runs in the first inning (over 0.5) and (c) a team's nine-inning runs (over 2.5 / 3.5 / 4.5)?

Data: MLB StatsAPI linescores (data/mlb_innings.py), regular seasons 2022-25 (free, no key). No free historical
baseball inning prices exist here, so this measures accuracy, not return.

Walk-forward, one-matchday purge: a game on day D is predicted from games dated BEFORE D-1 only; inning shares and
team ratings are refitted that way. Settings tried (rating shrink k x dispersion) are counted; the best are picked on
the FIRST test season and reported on the LATER ones only. Baseline = each team's plain average of the same quantity
(no shrinkage, league average below 5 games), same dispersion. Nothing here changes a pick, stake or threshold.

  python backtest/baseball_events_study.py
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import mlb_innings  # noqa: E402
from engine import baseball_events as be  # noqa: E402
from engine import event_model as em  # noqa: E402

OUT = ROOT / "backtest" / "BASEBALL_EVENTS_STUDY.md"
SEASONS = (2022, 2023, 2024, 2025)         # 2022 is history only
TEST = (2023, 2024, 2025)
K_GRID = (10.0, 30.0, 60.0, 120.0)
DISP_GRID = (4.0, 8.0, 16.0, math.inf)
INN_GRID = (0.6, 1.0, 1.5, math.inf)          # one inning's runs come in bunches: Poisson overstates P(a run)
EPS = 1e-4
GROUPS = (("first 5 innings total", "f5"), ("first inning scoreless", "inn1"), ("team runs", "team"))


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def _avg(vals: list[float], fallback: float) -> float:
    return sum(vals) / len(vals) if len(vals) >= 5 else fallback


class Baseline:
    """Each team's plain season average of the same quantity, from every prior game (no shrinkage)."""

    def __init__(self, hist: list[dict]):
        self.f5: dict = defaultdict(list)       # team -> both teams' runs in innings 1-5 in its games
        self.i1: dict = defaultdict(list)       # team -> both teams' runs in inning 1
        self.rf: dict = defaultdict(list)
        self.ra: dict = defaultdict(list)
        for r in hist:
            f5 = sum(x[0] + x[1] for x in r["r"][:5])
            i1 = r["r"][0][0] + r["r"][0][1]
            h, a = sum(x[0] for x in r["r"]), sum(x[1] for x in r["r"])
            for t in (r["home"], r["away"]):
                self.f5[t].append(f5)
                self.i1[t].append(i1)
            self.rf[r["home"]].append(h)
            self.ra[r["home"]].append(a)
            self.rf[r["away"]].append(a)
            self.ra[r["away"]].append(h)
        n = max(1, len(hist))
        self.lg_f5 = sum(sum(x[0] + x[1] for x in r["r"][:5]) for r in hist) / n
        self.lg_i1 = sum(r["r"][0][0] + r["r"][0][1] for r in hist) / n
        self.lg_team = sum(sum(x[0] + x[1] for x in r["r"]) for r in hist) / (2 * n)

    def f5_total(self, h: str, a: str) -> float:
        return (_avg(self.f5[h], self.lg_f5) + _avg(self.f5[a], self.lg_f5)) / 2

    def inn1_total(self, h: str, a: str) -> float:
        return (_avg(self.i1[h], self.lg_i1) + _avg(self.i1[a], self.lg_i1)) / 2

    def team_runs(self, h: str, a: str) -> tuple[float, float]:
        lg = self.lg_team
        return ((_avg(self.rf[h], lg) + _avg(self.ra[a], lg)) / 2, (_avg(self.rf[a], lg) + _avg(self.ra[h], lg)) / 2)


def run(games: list[dict], test_year: int, k: float, disp: float, collect: bool = False, idisp: float = be.DISP_INNING) -> dict:
    """Score every game of the test season: per-event sums of model and baseline log loss, paired per-game differences
    (for a standard error) and, with collect, calibration buckets of P(a run in the first inning)."""
    start, end = date(test_year, 3, 1).isoformat(), date(test_year, 12, 1).isoformat()
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in games:
        by_day[r["date"]].append(r)
    days = sorted(by_day)
    acc: dict[str, dict] = defaultdict(lambda: {"n": 0, "m": 0.0, "b": 0.0, "d": []})
    cal: dict[int, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    ci = 0
    hist: list[dict] = []
    last_cut = None
    shares = base = rat = None
    for day in days:
        if not (start <= day < end):
            continue
        cut = (datetime.fromisoformat(day) - timedelta(days=1)).date().isoformat()    # purge the previous matchday
        while ci < len(days) and days[ci] < cut:
            hist.extend(by_day[days[ci]])
            ci += 1
        if last_cut != cut:
            shares, base, rat, last_cut = be.fit_shares(hist), Baseline(hist), be.Ratings(hist), cut
        if shares is None or len(hist) < 300:
            continue                                                                  # PENDING (HR35): too little history
        sh, sa = shares
        for r in by_day[day]:
            rr = rat.rates(r["home"], r["away"], k)
            if rr is None:
                continue
            mh, ma = rr
            bh, ba = base.team_runs(r["home"], r["away"])
            ev: list[tuple[str, float, float, int]] = []
            f5 = sum(x[0] + x[1] for x in r["r"][:5])
            m5 = mh * sum(sh[:5]) + ma * sum(sa[:5])
            for line in be.LINES_F5:
                ev.append((f"f5 over {line}", em.over(line, m5, disp), em.over(line, base.f5_total(r["home"], r["away"]), disp), int(f5 > line)))
            i1 = r["r"][0][0] + r["r"][0][1]
            ev.append(("inn1 over 0.5", em.over(0.5, mh * sh[0] + ma * sa[0], idisp), em.over(0.5, base.inn1_total(r["home"], r["away"]), idisp), int(i1 > 0)))
            for side, mm, bb, idx in (("home", mh, bh, 0), ("away", ma, ba, 1)):
                got = sum(x[idx] for x in r["r"])
                for line in be.LINES_TEAM:
                    ev.append((f"team {side} over {line}", em.over(line, mm, disp), em.over(line, bb, disp), int(got > line)))
            for name, pm, pb, y in ev:
                a = acc[name]
                lm, lb = ll(pm, y), ll(pb, y)
                a["n"] += 1
                a["m"] += lm
                a["b"] += lb
                a["d"].append(lb - lm)
                if collect and name == "inn1 over 0.5":
                    c = cal[min(9, int(pm * 10))]
                    c[0] += 1
                    c[1] += pm
                    c[2] += y
    return {"acc": acc, "cal": cal}


def summarise(acc: dict, prefix: str) -> tuple[float, float, float, int]:
    """(model log loss, baseline log loss, standard error of the gap, n) over events whose name starts with prefix."""
    m = b = 0.0
    n = 0
    diffs: list[float] = []
    for key, a in acc.items():
        if key.startswith(prefix):
            m, b, n = m + a["m"], b + a["b"], n + a["n"]
            diffs += a["d"]
    if not n:
        return math.nan, math.nan, math.nan, 0
    mu = sum(diffs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in diffs) / max(1, n - 1))
    return m / n, b / n, sd / math.sqrt(n), n


def main() -> int:
    games: list[dict] = []
    for y in SEASONS:
        games += mlb_innings.season_rows(y)
    games.sort(key=lambda r: (r["date"], r["id"]))
    print(f"{len(games)} games with runs by inning")
    if len(games) < 6000:
        print("PENDING: not enough MLB games fetched; nothing written (HR35)")
        return 0
    first = TEST[0]
    tried = 0
    best: dict[str, tuple] = {}
    for k in K_GRID:                                   # step 1: shrink k per group (dispersion fixed at 8)
        tried += 1
        acc = run(games, first, k, 8.0)["acc"]
        for g, p in GROUPS:
            m = summarise(acc, p)[0]
            if g not in best or m < best[g][0]:
                best[g] = (m, k)
    chosen = {g: best[g][1] for g, _ in GROUPS}
    disp_pick = {g: 8.0 for g, _ in GROUPS}
    disp_best = {g: best[g][0] for g, _ in GROUPS}
    for disp in DISP_GRID:                             # step 2: dispersion per group at the chosen k
        if disp == 8.0:
            continue
        tried += 1
        for g, p in GROUPS:
            if g == "first inning scoreless":
                continue                               # tuned on its own grid below
            m = summarise(run(games, first, chosen[g], disp)["acc"], p)[0]
            if m < disp_best[g]:
                disp_pick[g], disp_best[g] = disp, m
    inn_disp = be.DISP_INNING
    inn_best = summarise(run(games, first, chosen["first inning scoreless"], 8.0, idisp=inn_disp)["acc"], "inn1")[0]
    for idisp in INN_GRID:
        if idisp == be.DISP_INNING:
            continue
        tried += 1
        m = summarise(run(games, first, chosen["first inning scoreless"], 8.0, idisp=idisp)["acc"], "inn1")[0]
        if m < inn_best:
            inn_disp, inn_best = idisp, m
    disp_pick["first inning scoreless"] = inn_disp
    lines = ["# Baseball events study (framework #587, record-only)", "",
             f"Written {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by backtest/baseball_events_study.py. SHADOW: nothing here picks, stakes or changes a rule.", "",
             f"Data: MLB StatsAPI linescores, {len(games)} regular-season games with nine or more innings, 2022-2025 (2022 history only). "
             "Nine-inning runs (extra innings excluded). No free historical baseball inning prices exist, so this measures accuracy, not return.", "",
             f"Walk-forward, one matchday purged. Settings tried: {tried} (rating shrink k x dispersion), picked on the FIRST test season "
             f"({first}) only: " + "; ".join(f"{g}: k={chosen[g]:g}, dispersion={disp_pick[g]:g}" for g, _ in GROUPS) + ". "
             "Log loss, lower is better; gap = baseline minus model (positive = model better), with its standard error.", ""]
    sh = be.fit_shares(games)
    if sh:
        lines += ["Inning shares of a side's runs (all games), home: " + ", ".join(f"{x:.3f}" for x in sh[0]) +
                  "; away: " + ", ".join(f"{x:.3f}" for x in sh[1]) + ".", ""]
    lines += ["| Test season | Event group | n events | Model | Baseline | Gap | s.e. |", "|---|---|---|---|---|---|---|"]
    verdict = []
    for y in TEST[1:]:
        for g, p in GROUPS:
            acc = run(games, y, chosen[g], disp_pick[g], idisp=inn_disp)["acc"]
            m, b, se, n = summarise(acc, p)
            lines.append(f"| {y} | {g} | {n} | {m:.4f} | {b:.4f} | {b - m:+.4f} | {se:.4f} |")
            verdict.append((g, b - m, se))
    lines += ["", "## Verdict (later test seasons only)", ""]
    for g, _ in GROUPS:
        gs = [(x, s) for lb, x, s in verdict if lb == g]
        x = sum(a for a, _ in gs) / len(gs)
        s = math.sqrt(sum(b * b for _, b in gs)) / len(gs)
        word = "BEATS the baseline" if x > 2 * s else "does NOT clearly beat the baseline"
        lines.append(f"- {g}: mean gap {x:+.4f} (s.e. {s:.4f}) - model {word}. Stays shadow until it does and the daily graded record agrees (order 53).")
    last = TEST[-1]
    cal = run(games, last, chosen["first inning scoreless"], 8.0, collect=True, idisp=inn_disp)["cal"]
    lines += ["", f"## Calibration, P(a run in the first inning), {last}", "", "| Bucket | n | Mean predicted | Observed |", "|---|---|---|---|"]
    for b in sorted(cal):
        n, sp, sy = cal[b]
        lines.append(f"| {b * 10}-{b * 10 + 10}% | {n} | {sp / n:.3f} | {sy / n:.3f} |")
    lines += ["", "Runs use a negative binomial with the dispersion above; a single inning uses its own, much clumpier dispersion (Poisson said 64% for a first-inning run when 50% happen). Starting pitchers are not an input "
              "(engine/mlb_pitcher.py is a separate shadow). The SportyBet market sweep (step 1 of #587), a winter-league feed and the Control "
              "Room reader need the live feed and are a follow-up: until the sweep logs which innings markets exist, no price is read or graded (HR35, HR59)."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
