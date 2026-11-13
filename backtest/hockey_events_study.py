"""
Ice hockey events study (framework #586, Event models #7; RECORD ONLY). Writes backtest/HOCKEY_EVENTS_STUDY.md.

Question: does the per-period model in engine/hockey_events.py (team ratings -> game goal rates -> the NHL's own
period shares) beat the plain two-teams' season-average baseline at (a) goals in a period (over 0.5 / 1.5, both
teams), (b) a team's regulation goals (over 1.5 / 2.5 / 3.5) and (c) shots on goal in a period?

Data: the NHL's own play-by-play (data/nhl_periods.py), regulation periods only, seasons 2022-25 (free, no key).
No free historical hockey prices exist (see ICE_HOCKEY_STUDY.md), so this measures accuracy, not return.

Walk-forward, one-matchday purge: a game on day D is predicted from games dated BEFORE D-1 only (the previous
matchday is left out); period shares, team ratings and the shot dispersion are all refitted that way. Settings tried
(rating shrink k x shot dispersion) are counted; the best pair is picked on the FIRST test season and reported on
the LATER ones only. Baseline = each team's plain average of the same quantity (home side: home team's goals for and
the away team's goals against, averaged), no shrinkage, no period shares beyond the team's own period average.
Nothing here changes a pick, stake or threshold.

  python backtest/hockey_events_study.py
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import nhl_periods  # noqa: E402
from engine import event_model as em  # noqa: E402
from engine import hockey_events as he  # noqa: E402

OUT = ROOT / "backtest" / "HOCKEY_EVENTS_STUDY.md"
SEASONS = (2022, 2023, 2024, 2025)         # 2022 is history only
TEST = (2023, 2024, 2025)
K_GRID = (10.0, 20.0, 40.0, 80.0)
DISP_GRID = (25.0, 60.0, 150.0, math.inf)
SHOT_LINES = (19.5, 21.5)                  # both teams' shots on goal in one period
EPS = 1e-4


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def _avg(vals: list[float], fallback: float) -> float:
    return sum(vals) / len(vals) if len(vals) >= 5 else fallback


class Baseline:
    """Each team's plain season average, built from every prior game (no shrinkage)."""

    def __init__(self, hist: list[dict]):
        self.pf: dict = defaultdict(list)     # (team, period, key) -> own per-game values (as home or away)
        self.pa: dict = defaultdict(list)
        self.tot: dict = defaultdict(list)
        for r in hist:
            for key in ("g", "s"):
                for i in range(3):
                    h, a = r[key][i]
                    self.tot[(r["home"], i, key)].append(h + a)
                    self.tot[(r["away"], i, key)].append(h + a)
                self.pf[(r["home"], key)].append(sum(x[0] for x in r[key]))
                self.pa[(r["home"], key)].append(sum(x[1] for x in r[key]))
                self.pf[(r["away"], key)].append(sum(x[1] for x in r[key]))
                self.pa[(r["away"], key)].append(sum(x[0] for x in r[key]))
        n = max(1, len(hist))
        self.lg = {(i, k): sum(sum(x[0] + x[1] for x in [r[k][i]]) for r in hist) / n for i in range(3) for k in ("g", "s")}
        self.lg_team = {k: sum(sum(x[0] + x[1] for x in r[k]) for r in hist) / (2 * n) for k in ("g", "s")}

    def period_total(self, home: str, away: str, i: int, key: str) -> float:
        lg = self.lg[(i, key)]
        return (_avg(self.tot[(home, i, key)], lg) + _avg(self.tot[(away, i, key)], lg)) / 2

    def team_goals(self, home: str, away: str) -> tuple[float, float]:
        lg = self.lg_team["g"]
        return ((_avg(self.pf[(home, "g")], lg) + _avg(self.pa[(away, "g")], lg)) / 2,
                (_avg(self.pf[(away, "g")], lg) + _avg(self.pa[(home, "g")], lg)) / 2)


def run(games: list[dict], test_year: int, k: float, disp: float, collect: bool = False) -> dict:
    """Score every game of the test season. Returns per-event sums of model and baseline log loss and the paired
    per-game differences (for a standard error), plus calibration buckets when collect=True."""
    start = date(test_year, 9, 1).isoformat()
    end = date(test_year + 1, 7, 1).isoformat()
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in games:
        by_day[r["date"]].append(r)
    days = sorted(by_day)
    acc: dict[str, dict] = defaultdict(lambda: {"n": 0, "m": 0.0, "b": 0.0, "d": []})
    cal: dict[int, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    cutoff_i = 0
    hist: list[dict] = []
    shares = None
    base = None
    last_cut = None
    for day in days:
        if not (start <= day < end):
            continue
        cut = (datetime.fromisoformat(day) - timedelta(days=1)).date().isoformat()   # purge the previous matchday
        while cutoff_i < len(days) and days[cutoff_i] < cut:
            hist.extend(by_day[days[cutoff_i]])
            cutoff_i += 1
        if last_cut != cut:
            shares, base, last_cut = he.fit_shares(hist), Baseline(hist), cut
            rg_all, rs_all = he.Ratings(hist, "g"), he.Ratings(hist, "s")
        if shares is None or len(hist) < 300:
            continue                                                             # PENDING (HR35): too little history
        sg, ss = shares
        for r in by_day[day]:
            rg = rg_all.rates(r["home"], r["away"], k)
            rs = rs_all.rates(r["home"], r["away"], k)
            if rg is None or rs is None:
                continue
            lh, la = rg
            sh, sa = rs
            bh, ba = base.team_goals(r["home"], r["away"])
            ev: list[tuple[str, float, float, int]] = []
            for i in range(3):
                tot_g = r["g"][i][0] + r["g"][i][1]
                tot_s = r["s"][i][0] + r["s"][i][1]
                mm = (lh + la) * sg[i]
                bb = base.period_total(r["home"], r["away"], i, "g")
                for line in (0.5, 1.5):
                    ev.append((f"goals P{i + 1} over {line}", he.pois_over(line, mm), he.pois_over(line, bb), int(tot_g > line)))
                ms = (sh + sa) * ss[i]
                bs = base.period_total(r["home"], r["away"], i, "s")
                for line in SHOT_LINES:
                    ev.append((f"shots P{i + 1} over {line}", em.over(line, ms, disp), em.over(line, bs, disp), int(tot_s > line)))
            for side, mm, bb, idx in (("home", lh, bh, 0), ("away", la, ba, 1)):
                got = sum(x[idx] for x in r["g"])
                for line in he.LINES_TEAM:
                    ev.append((f"{side} team goals over {line}", he.pois_over(line, mm), he.pois_over(line, bb), int(got > line)))
            for name, pm, pb, y in ev:
                a = acc[name]
                lm, lb = ll(pm, y), ll(pb, y)
                a["n"] += 1
                a["m"] += lm
                a["b"] += lb
                a["d"].append(lb - lm)
                if collect and name.startswith("goals P1 over 0.5"):
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
    for k, a in acc.items():
        if k.startswith(prefix):
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
        games += nhl_periods.season_rows(y)
    games.sort(key=lambda r: (r["date"], r["id"]))
    print(f"{len(games)} games with per-period goals and shots")
    if len(games) < 1500:
        print("PENDING: not enough NHL games fetched; nothing written (HR35)")
        return 0
    first = TEST[0]
    tried = 0
    best: dict[str, tuple] = {}
    for k in K_GRID:                                   # step 1: shrink k per group (shot dispersion fixed at 60)
        tried += 1
        acc = run(games, first, k, 60.0)["acc"]
        for part in ("goals", "home team", "shots"):
            m, *_ = summarise(acc, part)
            if part not in best or m < best[part][0]:
                best[part] = (m, k)
    k_g, k_t, k_s = best["goals"][1], best["home team"][1], best["shots"][1]
    d_s, d_best = 60.0, summarise(run(games, first, k_s, 60.0)["acc"], "shots")[0]
    for disp in DISP_GRID:                             # step 2: shot dispersion at the chosen shots k
        if disp == 60.0:
            continue
        tried += 1
        m = summarise(run(games, first, k_s, disp)["acc"], "shots")[0]
        if m < d_best:
            d_s, d_best = disp, m
    lines = ["# Ice hockey events study (framework #586, record-only)", "",
             f"Written {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by backtest/hockey_events_study.py. SHADOW: nothing here picks, stakes or changes a rule.", "",
             f"Data: NHL play-by-play, regulation periods, {len(games)} regular-season games, seasons 2022-23 to 2025-26 (2022-23 history only).",
             "No free historical hockey prices exist, so this measures accuracy, not return.", "",
             f"Walk-forward, one matchday purged. Settings tried: {tried} (rating shrink k x shot dispersion), picked on the "
             f"FIRST test season ({first}-{str(first + 1)[2:]}) only: goals k={k_g:g}, home-team totals k={k_t:g}, shots k={k_s:g} dispersion={d_s:g}. "
             "Log loss, lower is better; gap = baseline minus model (positive = model better), with its standard error.", ""]
    shares_all = he.fit_shares(games)
    if shares_all:
        lines += ["Period shares of regulation goals / shots on goal (all games): "
                  f"goals {', '.join(f'{x:.3f}' for x in shares_all[0])}; shots {', '.join(f'{x:.3f}' for x in shares_all[1])}.", ""]
    lines += ["| Test season | Event group | n events | Model | Baseline | Gap | s.e. |", "|---|---|---|---|---|---|---|"]
    verdict = []
    for y in TEST[1:]:
        for label, prefix, kk, dd in (("goals in a period", "goals", k_g, math.inf), ("team goals", "home team", k_t, math.inf),
                                      ("shots in a period", "shots", k_s, d_s)):
            acc = run(games, y, kk, dd)["acc"]
            if prefix == "home team":
                m1, b1, s1, n1 = summarise(acc, "home team")
                m2, b2, s2, n2 = summarise(acc, "away team")
                n = n1 + n2
                m, b = (m1 * n1 + m2 * n2) / n, (b1 * n1 + b2 * n2) / n
                se = math.sqrt((s1 * n1) ** 2 + (s2 * n2) ** 2) / n
            else:
                m, b, se, n = summarise(acc, prefix)
            gap = b - m
            lines.append(f"| {y}-{str(y + 1)[2:]} | {label} | {n} | {m:.4f} | {b:.4f} | {gap:+.4f} | {se:.4f} |")
            verdict.append((label, gap, se))
    lines += ["", "## Verdict (later test seasons only)", ""]
    for label in ("goals in a period", "team goals", "shots in a period"):
        gs = [(g, s) for lb, g, s in verdict if lb == label]
        if not gs:
            continue
        g = sum(x for x, _ in gs) / len(gs)
        s = math.sqrt(sum(x * x for _, x in gs)) / len(gs)
        word = "BEATS the baseline" if g > 2 * s else "does NOT clearly beat the baseline"
        lines.append(f"- {label}: mean gap {g:+.4f} (s.e. {s:.4f}) - model {word}. Stays shadow until it does and the daily graded record agrees (order 53).")
    last = TEST[-1]
    cal = run(games, last, k_g, math.inf, collect=True)["cal"]
    lines += ["", f"## Calibration, P(period 1 has a goal) {last}-{str(last + 1)[2:]}", "", "| Bucket | n | Mean predicted | Observed |", "|---|---|---|---|"]
    for b in sorted(cal):
        n, sp, sy = cal[b]
        lines.append(f"| {b * 10}-{b * 10 + 10}% | {n} | {sp / n:.3f} | {sy / n:.3f} |")
    lines += ["", "Shots lines use a negative binomial with the dispersion above; goals use Poisson. Player events are out of scope.",
              "Control Room reader and the SportyBet market-name sweep (step 1 of #586) need the live feed and are a follow-up: "
              "until the sweep logs which period markets exist, no price is read or graded (HR35, HR59)."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
