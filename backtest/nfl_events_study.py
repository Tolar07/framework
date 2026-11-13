"""
NFL events study (framework #588, Event models #9; RECORD ONLY). Writes backtest/NFL_EVENTS_STUDY.md.

Question: does the model in engine/nfl_events.py (team points ratings -> regulation means -> the NFL's own quarter
shares) beat the plain two-teams' season-average baseline at (a) one quarter's total points (both teams), (b) a half's
total points and (c) a team's regulation points?

Data: ESPN scoreboard quarter scores (data/nfl_quarters.py), regular seasons 2019-25 (free, no key). No free historical
quarter / half prices exist here, so this measures accuracy, not return.

Walk-forward, one-matchday purge: a game on day D is predicted from games dated BEFORE D-1 only; quarter shares and team
ratings are refitted that way. Settings tried (rating shrink k x dispersion per group) are counted; the best are picked on
the FIRST test season and reported on the LATER ones only. Baseline = each team's plain average of the same quantity
(no shrinkage, league average below 5 games), same dispersion. Nothing here changes a pick, stake or threshold.

  python backtest/nfl_events_study.py
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import nfl_quarters  # noqa: E402
from engine import event_model as em  # noqa: E402
from engine import nfl_events as ne  # noqa: E402

OUT = ROOT / "backtest" / "NFL_EVENTS_STUDY.md"
SEASONS = (2019, 2020, 2021, 2022, 2023, 2024, 2025)    # 2019-21 are history only
TEST = (2022, 2023, 2024, 2025)
K_GRID = (8.0, 17.0, 34.0, 68.0)
DISP_GRID = (0.75, 1.5, 3.0, 6.0, 12.0, math.inf)
EPS = 1e-4
GROUPS = (("quarter totals", "q"), ("half totals", "h"), ("team points", "team"))
DEFAULT = {"quarter totals": ne.DISP_QUARTER, "half totals": ne.DISP_HALF, "team points": ne.DISP_TEAM}


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def _avg(vals: list[float], fallback: float) -> float:
    return sum(vals) / len(vals) if len(vals) >= 5 else fallback


class Baseline:
    """Each team's plain season average of the same quantity, from every prior game (no shrinkage)."""

    def __init__(self, hist: list[dict]):
        self.q: dict = defaultdict(lambda: [[] for _ in range(4)])    # team -> per quarter, both teams' points in its games
        self.rf: dict = defaultdict(list)
        self.ra: dict = defaultdict(list)
        lq = [0.0] * 4
        lt = 0.0
        for r in hist:
            for i in range(4):
                tot = r["r"][i][0] + r["r"][i][1]
                lq[i] += tot
                self.q[r["home"]][i].append(tot)
                self.q[r["away"]][i].append(tot)
            h, a = sum(x[0] for x in r["r"]), sum(x[1] for x in r["r"])
            lt += h + a
            self.rf[r["home"]].append(h)
            self.ra[r["home"]].append(a)
            self.rf[r["away"]].append(a)
            self.ra[r["away"]].append(h)
        n = max(1, len(hist))
        self.lg_q = [x / n for x in lq]
        self.lg_team = lt / (2 * n)

    def quarter(self, h: str, a: str, i: int) -> float:
        return (_avg(self.q[h][i], self.lg_q[i]) + _avg(self.q[a][i], self.lg_q[i])) / 2

    def team_points(self, h: str, a: str) -> tuple[float, float]:
        lg = self.lg_team
        return ((_avg(self.rf[h], lg) + _avg(self.ra[a], lg)) / 2, (_avg(self.rf[a], lg) + _avg(self.ra[h], lg)) / 2)


def run(games: list[dict], test_year: int, k: float, disp: dict, collect: bool = False) -> dict:
    """Score every game of the test season (August to July): per-event sums of model and baseline log loss, paired
    per-game differences (for a standard error) and, with collect, calibration buckets of P(first half over 23.5)."""
    start, end = date(test_year, 8, 1).isoformat(), date(test_year + 1, 8, 1).isoformat()
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
            shares, base, rat, last_cut = ne.fit_shares(hist), Baseline(hist), ne.Ratings(hist), cut
        if shares is None or len(hist) < 200:
            continue                                                                  # PENDING (HR35): too little history
        sh, sa = shares
        for r in by_day[day]:
            rr = rat.rates(r["home"], r["away"], k)
            if rr is None:
                continue
            mh, ma = rr
            bh, ba = base.team_points(r["home"], r["away"])
            ev: list[tuple[str, float, float, int]] = []
            for i in range(4):
                got = r["r"][i][0] + r["r"][i][1]
                m = mh * sh[i] + ma * sa[i]
                for line in ne.LINES_QUARTER:
                    ev.append((f"q{i + 1} over {line}", em.over(line, m, disp["quarter totals"]),
                               em.over(line, base.quarter(r["home"], r["away"], i), disp["quarter totals"]), int(got > line)))
            for name, lo in (("1h", 0), ("2h", 2)):
                got = sum(r["r"][i][0] + r["r"][i][1] for i in (lo, lo + 1))
                m = mh * sum(sh[lo:lo + 2]) + ma * sum(sa[lo:lo + 2])
                b = sum(base.quarter(r["home"], r["away"], i) for i in (lo, lo + 1))
                for line in ne.LINES_HALF:
                    pm = em.over(line, m, disp["half totals"])
                    ev.append((f"h {name} over {line}", pm, em.over(line, b, disp["half totals"]), int(got > line)))
                    if collect and name == "1h" and line == 23.5:
                        c = cal[min(9, int(pm * 10))]
                        c[0] += 1
                        c[1] += pm
                        c[2] += int(got > line)
            for side, mm, bb, idx in (("home", mh, bh, 0), ("away", ma, ba, 1)):
                got = sum(x[idx] for x in r["r"])
                for line in ne.LINES_TEAM:
                    ev.append((f"team {side} over {line}", em.over(line, mm, disp["team points"]),
                               em.over(line, bb, disp["team points"]), int(got > line)))
            for name, pm, pb, y in ev:
                a = acc[name]
                lm, lb = ll(pm, y), ll(pb, y)
                a["n"] += 1
                a["m"] += lm
                a["b"] += lb
                a["d"].append(lb - lm)
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
        games += nfl_quarters.season_rows(y)
    games.sort(key=lambda r: (r["date"], r["id"]))
    print(f"{len(games)} games with points by quarter")
    if len(games) < 1500:
        print("PENDING: not enough NFL games fetched; nothing written (HR35)")
        return 0
    first = TEST[0]
    tried = 0
    best: dict[str, tuple] = {}
    for k in K_GRID:                                   # step 1: shrink k per group (default dispersion)
        tried += 1
        acc = run(games, first, k, DEFAULT)["acc"]
        for g, p in GROUPS:
            m = summarise(acc, p)[0]
            if g not in best or m < best[g][0]:
                best[g] = (m, k)
    chosen = {g: best[g][1] for g, _ in GROUPS}
    disp_pick = dict(DEFAULT)
    disp_best = {g: best[g][0] for g, _ in GROUPS}
    for disp in DISP_GRID:                             # step 2: dispersion per group at the chosen k
        tried += 1
        for g, p in GROUPS:
            trial = dict(DEFAULT)
            trial[g] = disp
            m = summarise(run(games, first, chosen[g], trial)["acc"], p)[0]
            if m < disp_best[g]:
                disp_pick[g], disp_best[g] = disp, m
    lines = ["# NFL events study (framework #588, record-only)", "",
             f"Written {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by backtest/nfl_events_study.py. SHADOW: nothing here picks, stakes or changes a rule.", "",
             f"Data: ESPN scoreboard quarter scores, {len(games)} regular-season games, 2019-2025 (2019-21 history only). "
             "Regulation points only (overtime excluded). No free historical quarter or half prices exist, so this measures accuracy, not return.", "",
             f"Walk-forward, one matchday purged. Settings tried: {tried} (rating shrink k x dispersion), picked on the FIRST test season "
             f"({first}) only: " + "; ".join(f"{g}: k={chosen[g]:g}, dispersion={disp_pick[g]:g}" for g, _ in GROUPS) + ". "
             "Log loss, lower is better; gap = baseline minus model (positive = model better), with its standard error.", ""]
    sh = ne.fit_shares(games)
    if sh:
        lines += ["Quarter shares of a side's regulation points (all games), home: " + ", ".join(f"{x:.3f}" for x in sh[0]) +
                  "; away: " + ", ".join(f"{x:.3f}" for x in sh[1]) + ".", ""]
    lines += ["| Test season | Event group | n events | Model | Baseline | Gap | s.e. |", "|---|---|---|---|---|---|---|"]
    verdict = []
    for y in TEST[1:]:
        for g, p in GROUPS:
            d = dict(DEFAULT)
            d[g] = disp_pick[g]
            m, b, se, n = summarise(run(games, y, chosen[g], d)["acc"], p)
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
    d = dict(DEFAULT)
    d.update(disp_pick)
    cal = run(games, last, chosen["half totals"], d, collect=True)["cal"]
    lines += ["", f"## Calibration, P(first half over 23.5), {last}", "", "| Bucket | n | Mean predicted | Observed |", "|---|---|---|---|"]
    for b in sorted(cal):
        n, sp, sy = cal[b]
        lines.append(f"| {b * 10}-{b * 10 + 10}% | {n} | {sp / n:.3f} | {sy / n:.3f} |")
    lines += ["", "Points use a negative binomial with the dispersion above (they come in 3s and 7s). Weather, injuries and the quarterback are not "
              "inputs. Team rates here are points for / against from past games; engine/nfl_events.from_total() takes the board's own total and "
              "spread instead (a test shows they add up). The SportyBet market sweep (step 1 of #588), the NCAAF run, the basketball-parity "
              "wiring of the quarter markets and the Control Room reader need the live feed and are a follow-up: until the sweep logs which "
              "quarter / half markets exist, no price is read or graded (HR35, HR59)."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
