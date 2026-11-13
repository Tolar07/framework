"""
Cricket events study (framework #589, Event models #10; RECORD ONLY). Writes backtest/CRICKET_EVENTS_STUDY.md.

Question: does the model in engine/cricket_events.py (batting team's runs for x bowling team's runs against x venue, each
shrunk to the format average; over-block shares from the record) beat the plain two-teams' average baseline at (a) a side's
first-innings total runs, (b) runs in an over block (T20 overs 1-6 / 7-15 / 16-20; ODI 1-10 / 11-40 / 41-50) and
(c) wickets lost in the first innings?

Data: Cricsheet ball-by-ball (data/cricket_overs.py), men's T20 and ODI internationals, first innings that ran its course.
No free historical total / block / wicket prices exist here, so this measures accuracy, not return.

Walk-forward, one-matchday purge: a match on day D is predicted from matches dated BEFORE D-1 only; ratings and shares are
refitted that way. Settings tried (team shrink k x venue shrink kv; dispersion per group) are counted and picked on the FIRST
test year only; the later years are reported with those settings. Baseline = the batting team's plain average of the same
quantity averaged with the bowling team's plain average conceded (no shrinkage, no venue; format average below 5 matches),
same dispersion. Nothing here changes a pick, stake or threshold.

  python backtest/cricket_events_study.py
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import cricket_overs  # noqa: E402
from engine import cricket_events as ce  # noqa: E402
from engine import event_model as em  # noqa: E402

OUT = ROOT / "backtest" / "CRICKET_EVENTS_STUDY.md"
FIRST, LAST = 2019, 2026          # first test year picks the settings; later years are reported
K_GRID = (5.0, 10.0, 20.0, 40.0)
KV_GRID = (10.0, 30.0, 1e9)       # 1e9 = no venue effect
DISP_RUNS = (10.0, 20.0, 40.0, 80.0, math.inf)
DISP_WK = (5.0, 10.0, 20.0, 40.0, math.inf)
EPS = 1e-4
GROUPS = (("total runs", "total"), ("over-block runs", "block"), ("wickets", "wk"))
MIN_HIST = 100


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def _avg(vals: list[float], fallback: float) -> float:
    return sum(vals) / len(vals) if len(vals) >= 5 else fallback


class Baseline:
    """Each team's plain average of the same quantity (4 numbers: three blocks and wickets) from every prior innings."""

    def __init__(self, hist: list[dict]):
        self.bat: dict = defaultdict(lambda: [[] for _ in range(4)])
        self.bowl: dict = defaultdict(lambda: [[] for _ in range(4)])
        tot = [0.0] * 4
        for r in hist:
            q = [*r["blocks"], r["wk"]]
            for i in range(4):
                tot[i] += q[i]
                self.bat[r["bat"]][i].append(q[i])
                self.bowl[r["bowl"]][i].append(q[i])
        n = max(1, len(hist))
        self.lg = [x / n for x in tot]

    def mean(self, bat: str, bowl: str, i: int) -> float:
        return (_avg(self.bat[bat][i], self.lg[i]) + _avg(self.bowl[bowl][i], self.lg[i])) / 2


def run(rows: list[dict], fmt: str, year: int, k: float, kv: float, d_runs: dict, d_wk: float, collect: bool = False) -> dict:
    """Score every first innings of one format in a calendar year: per-event sums of model and baseline log loss and the
    paired per-innings differences; with collect, calibration buckets of P(total over the middle line)."""
    rows = [r for r in rows if r["fmt"] == fmt]
    start, end = f"{year}-01-01", f"{year + 1}-01-01"
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)
    days = sorted(by_day)
    acc: dict[str, dict] = defaultdict(lambda: {"n": 0, "m": 0.0, "b": 0.0, "d": []})
    cal: dict[int, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    hist: list[dict] = []
    ci = 0
    last_cut = None
    shares = base = rat = None
    mid = ce.LINES_TOTAL[fmt][1]
    for day in days:
        if not (start <= day < end):
            continue
        cut = (datetime.fromisoformat(day) - timedelta(days=1)).date().isoformat()     # purge the previous matchday
        while ci < len(days) and days[ci] < cut:
            hist.extend(by_day[days[ci]])
            ci += 1
        if last_cut != cut:
            shares, base, rat, last_cut = ce.fit_shares(hist), Baseline(hist), ce.Ratings(hist), cut
        if shares is None or len(hist) < MIN_HIST:
            continue                                                                    # PENDING (HR35): too little history
        for r in by_day[day]:
            rr = rat.rates(r["bat"], r["bowl"], r["venue"], k, kv)
            if rr is None:
                continue
            mr, mw = rr
            ev: list[tuple[str, float, float, int]] = []
            got_t = sum(r["blocks"])
            bt = sum(base.mean(r["bat"], r["bowl"], i) for i in range(3))
            for line in ce.LINES_TOTAL[fmt]:
                ev.append((f"total {line}", em.over(line, mr, d_runs["total runs"]), em.over(line, bt, d_runs["total runs"]), int(got_t > line)))
                if collect and line == mid:
                    c = cal[min(9, int(ev[-1][1] * 10))]
                    c[0] += 1
                    c[1] += ev[-1][1]
                    c[2] += int(got_t > line)
            for i in range(3):
                for line in ce.LINES_BLOCK[fmt][i]:
                    ev.append((f"block{i + 1} {line}", em.over(line, mr * shares[i], d_runs["over-block runs"]),
                               em.over(line, base.mean(r["bat"], r["bowl"], i), d_runs["over-block runs"]), int(r["blocks"][i] > line)))
            for line in ce.LINES_WICKETS[fmt]:
                ev.append((f"wk {line}", em.over(line, mw, d_wk), em.over(line, base.mean(r["bat"], r["bowl"], 3), d_wk), int(r["wk"] > line)))
            for name, pm, pb, y in ev:
                a = acc[name]
                lm, lb = ll(pm, y), ll(pb, y)
                a["n"] += 1
                a["m"] += lm
                a["b"] += lb
                a["d"].append(lb - lm)
    return {"acc": acc, "cal": cal}


def merge(*accs: dict) -> dict:
    out: dict[str, dict] = defaultdict(lambda: {"n": 0, "m": 0.0, "b": 0.0, "d": []})
    for acc in accs:
        for key, a in acc.items():
            o = out[key]
            o["n"] += a["n"]
            o["m"] += a["m"]
            o["b"] += a["b"]
            o["d"] += a["d"]
    return out


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


def _year(rows: list[dict], year: int, k: float, kv: float, d_runs: dict, d_wk: float, collect: bool = False) -> dict:
    parts = [run(rows, f, year, k, kv, d_runs, d_wk, collect) for f in ("T20", "ODI")]
    cal: dict[int, list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for p in parts[:1]:                                  # calibration is shown for T20 (the format with most innings)
        for b, v in p["cal"].items():
            for j in range(3):
                cal[b][j] += v[j]
    return {"acc": merge(*[p["acc"] for p in parts]), "cal": cal}


def main() -> int:
    rows = cricket_overs.load()
    n_t20, n_odi = sum(r["fmt"] == "T20" for r in rows), sum(r["fmt"] == "ODI" for r in rows)
    print(f"{len(rows)} first innings ({n_t20} T20, {n_odi} ODI)")
    if n_t20 < 1000 or n_odi < 500:
        print("PENDING: not enough Cricsheet innings fetched; nothing written (HR35)")
        return 0
    default = {"total runs": ce.DISP_TOTAL["T20"], "over-block runs": ce.DISP_BLOCK["T20"]}
    tried = 0
    best = None
    for k in K_GRID:                                     # step 1: team shrink k x venue shrink kv, scored on total runs
        for kv in KV_GRID:
            tried += 1
            m = summarise(_year(rows, FIRST, k, kv, default, ce.DISP_WK)["acc"], "total")[0]
            if best is None or m < best[0]:
                best = (m, k, kv)
    _, k, kv = best
    disp = dict(default)
    disp_wk = ce.DISP_WK
    scores = {g: summarise(_year(rows, FIRST, k, kv, disp, disp_wk)["acc"], p)[0] for g, p in GROUPS}
    for d in DISP_RUNS:                                  # step 2: dispersion per group at the chosen k, kv
        tried += 1
        for g in ("total runs", "over-block runs"):
            trial = dict(disp)
            trial[g] = d
            m = summarise(_year(rows, FIRST, k, kv, trial, disp_wk)["acc"], dict(GROUPS)[g])[0]
            if m < scores[g]:
                scores[g], default[g] = m, d
    disp = dict(default)
    for d in DISP_WK:
        tried += 1
        m = summarise(_year(rows, FIRST, k, kv, disp, d)["acc"], "wk")[0]
        if m < scores["wickets"]:
            scores["wickets"], disp_wk = m, d
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    L = ["# Cricket events study (framework #589, record-only)", "",
         f"Written {made} UTC by backtest/cricket_events_study.py. SHADOW: nothing here picks, stakes or changes a rule.", "",
         f"Data: Cricsheet ball-by-ball (CC BY 4.0), {len(rows)} men's international first innings that ran their course ({n_t20} T20, {n_odi} ODI). "
         "Only the first innings counts (a chase stops at the target). No free historical total / block / wicket prices exist, so this measures accuracy, not return.", "",
         f"Walk-forward, one matchday purged. Settings tried: {tried} (team shrink k x venue shrink kv; dispersion per group), picked on the FIRST test year "
         f"({FIRST}) only: k={k:g}, venue kv={'none' if kv > 1e6 else f'{kv:g}'}; dispersion total={disp['total runs']:g}, block={disp['over-block runs']:g}, wickets={disp_wk:g}. "
         "Log loss, lower is better; gap = baseline minus model (positive = model better), with its standard error.", ""]
    for fmt, shs in (("T20", cricket_overs_shares(rows, "T20")), ("ODI", cricket_overs_shares(rows, "ODI"))):
        if shs:
            L.append(f"{fmt} block shares of first-innings runs (all data): " + ", ".join(f"{x:.3f}" for x in shs) + ".")
    L += ["", "| Test year | Event group | n events | Model | Baseline | Gap | s.e. |", "|---|---|---|---|---|---|---|"]
    verdict: list[tuple[str, float, float]] = []
    pooled = []
    for y in range(FIRST + 1, LAST + 1):
        acc = _year(rows, y, k, kv, disp, disp_wk)["acc"]
        pooled.append(acc)
        for g, p in GROUPS:
            m, b, se, n = summarise(acc, p)
            if n:
                L.append(f"| {y} | {g} | {n} | {m:.4f} | {b:.4f} | {b - m:+.4f} | {se:.4f} |")
    allacc = merge(*pooled)
    L += ["", f"## Verdict (all later test years pooled, {FIRST + 1}-{LAST})", ""]
    for g, p in GROUPS:
        m, b, se, n = summarise(allacc, p)
        if not n:
            L.append(f"- {g}: PENDING (no events scored).")
            continue
        word = "BEATS the baseline" if (b - m) > 2 * se else "does NOT clearly beat the baseline"
        L.append(f"- {g}: model {m:.4f} vs baseline {b:.4f}, gap {b - m:+.4f} (s.e. {se:.4f}, n={n}) - model {word}. "
                 "Stays shadow until it does and the daily graded record agrees (order 53).")
        verdict.append((g, b - m, se))
    cal = _year(rows, LAST, k, kv, disp, disp_wk, collect=True)["cal"]
    L += ["", f"## Calibration, T20 P(first-innings total over {ce.LINES_TOTAL['T20'][1]}), {LAST}", "",
          "| Bucket | n | Mean predicted | Observed |", "|---|---|---|---|"]
    for b in sorted(cal):
        n, sp, sy = cal[b]
        L.append(f"| {b * 10}-{b * 10 + 10}% | {int(n)} | {sp / n:.3f} | {sy / n:.3f} |")
    L += ["", "Weather, pitch, toss and line-ups are not inputs (not in Cricsheet); venue stands in for the pitch. Tests, Twenty20 leagues "
          "(IPL, BBL) and women's cricket are left out of this first run. The SportyBet market sweep (step 1 of #589), the basketball-parity "
          "wiring and the Control Room reader need the live feed and are a follow-up: until the sweep logs which total / over-block / wicket "
          "markets exist, no price is read or graded (HR35, HR59)."]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


def cricket_overs_shares(rows: list[dict], fmt: str):
    return ce.fit_shares([r for r in rows if r["fmt"] == fmt])


if __name__ == "__main__":
    raise SystemExit(main())
