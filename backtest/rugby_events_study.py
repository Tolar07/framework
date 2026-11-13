"""
Rugby events study (framework #593, Event models #14; RECORD ONLY). Writes backtest/RUGBY_EVENTS_STUDY.md.

Question: does engine/rugby_events.py (team points ratings -> expected points -> the fitted first-half share and per-point
try / penalty-goal rates) beat each team's plain average of the same quantity at (a) first-half total points, (b) total
tries and a team's tries and (c) total penalty goals? Data: ESPN rugby scoreboard (data/rugby_events.py). A real half split
exists almost only for 2014-15, and try / penalty counts that rebuild the score for about the same games, so the sample is small;
every number below carries its n and standard error. No free historical half / try price exists: accuracy, not return.

Walk-forward, one-matchday purge: a game on day D sees only games dated before D-1 (shares, rates, ratings and baseline all
refitted that way). The first WARM games are history only; the next TUNE games choose the settings (rating shrink k x
dispersion, all counted); the rest are the held-out test. Nothing here changes a pick, stake or threshold.

  python backtest/rugby_events_study.py
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import rugby_events as data  # noqa: E402
from engine import event_model as em  # noqa: E402
from engine import rugby_events as re_  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_EVENTS_STUDY.md"
WARM, TUNE, MIN_HIST = 250, 120, 150
K_GRID = (4.0, 8.0, 16.0, 32.0)
DISP_GRID = (4.0, 10.0, 30.0, math.inf)
EPS = 1e-4
GROUPS = (("first-half total points", "h1"), ("tries", "tr"), ("penalty goals", "pg"))
PREFIX = {"h1": "h1 ", "tr": "tries", "pg": "pens"}
KINDS = ("h1", "tries", "pens")


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def _avg(v: list[float], fb: float) -> float:
    return sum(v) / len(v) if len(v) >= 5 else fb


class Baseline:
    """Each team's plain average of the same quantity from every prior game (league average below 5 games)."""

    def __init__(self, hist: list[dict]):
        self.q: dict = {k: defaultdict(list) for k in KINDS}      # both sides' total in the team's games
        self.f: dict = {k: defaultdict(list) for k in KINDS}      # the team's own
        self.a: dict = {k: defaultdict(list) for k in KINDS}      # its opponents'
        tot = {k: 0.0 for k in KINDS}
        cnt = {k: 0 for k in KINDS}
        for r in hist:
            for kind in KINDS:
                v = r.get(kind)
                if v is None:
                    continue
                self.q[kind][r["home"]].append(v[0] + v[1])
                self.q[kind][r["away"]].append(v[0] + v[1])
                self.f[kind][r["home"]].append(v[0])
                self.a[kind][r["home"]].append(v[1])
                self.f[kind][r["away"]].append(v[1])
                self.a[kind][r["away"]].append(v[0])
                tot[kind] += v[0] + v[1]
                cnt[kind] += 1
        self.lg = {k: (tot[k] / cnt[k] if cnt[k] else 0.0) for k in KINDS}

    def total(self, kind: str, h: str, a: str) -> float:
        return (_avg(self.q[kind][h], self.lg[kind]) + _avg(self.q[kind][a], self.lg[kind])) / 2

    def team(self, kind: str, h: str, a: str) -> tuple[float, float]:
        lg = self.lg[kind] / 2
        return ((_avg(self.f[kind][h], lg) + _avg(self.a[kind][a], lg)) / 2,
                (_avg(self.f[kind][a], lg) + _avg(self.a[kind][h], lg)) / 2)


def run(games: list[dict], lo: int, hi: int, k: float, disp: float) -> dict:
    """Score games[lo:hi]: per event name the model / baseline log-loss sums and paired differences."""
    by_day: dict[str, list[dict]] = defaultdict(list)
    for g in games:
        by_day[g["day"]].append(g)
    days = sorted(by_day)
    targets = {id(g) for g in games[lo:hi]}
    acc: dict[str, dict] = defaultdict(lambda: {"n": 0, "m": 0.0, "b": 0.0, "d": []})
    cal: list[tuple[float, int]] = []
    hist: list[dict] = []
    ci = 0
    last = None
    fit = base = rat = None
    for day in days:
        day_games = [g for g in by_day[day] if id(g) in targets]
        if not day_games:
            continue
        cut = (datetime.fromisoformat(day) - timedelta(days=1)).date().isoformat()
        while ci < len(days) and days[ci] < cut:
            hist.extend(by_day[days[ci]])
            ci += 1
        if last != cut:
            fit, base, rat, last = re_.fit(hist), Baseline(hist), re_.Ratings(hist), cut
        if fit is None or len(hist) < MIN_HIST:
            continue
        for g in day_games:
            rr = rat.rates(g["home"], g["away"], k)
            if rr is None:
                continue
            mh, ma = rr
            ev: list[tuple[str, float, float, int]] = []
            m = mh * fit["share"][0] + ma * fit["share"][1]
            b = base.total("h1", g["home"], g["away"])
            got = g["h1"][0] + g["h1"][1]
            for ln in re_.LINES_HALF:
                ev.append((f"h1 over {ln}", em.over(ln, m, disp), em.over(ln, b, disp), int(got > ln)))
            if fit["rate"] and g.get("tries"):
                for name, key, lines in (("tries", "tries", re_.LINES_TRIES), ("pens", "pens", re_.LINES_PENS)):
                    rate = fit["rate"][key]
                    got = g[key][0] + g[key][1]
                    for ln in lines:
                        ev.append((f"{name} over {ln}", em.over(ln, (mh + ma) * rate, disp),
                                   em.over(ln, base.total(key, g["home"], g["away"]), disp), int(got > ln)))
                bh, ba = base.team("tries", g["home"], g["away"])
                for side, mm, bb, i in (("home", mh, bh, 0), ("away", ma, ba, 1)):
                    for ln in re_.LINES_TEAM_TRIES:
                        ev.append((f"tries team {side} over {ln}", em.over(ln, mm * fit["rate"]["tries"], disp),
                                   em.over(ln, bb, disp), int(g["tries"][i] > ln)))
            for name, pm, pb, y in ev:
                a = acc[name]
                lm, lb = ll(pm, y), ll(pb, y)
                a["n"] += 1
                a["m"] += lm
                a["b"] += lb
                a["d"].append(lb - lm)
                if name == "h1 over 20.5":
                    cal.append((pm, y))
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


def render(games: list[dict], now: datetime) -> str:
    L = ["# Rugby events study (first-half total points, tries, penalty goals)", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/rugby_events_study.py` (framework #593). SHADOW, record only; "
         "no price in the source, so accuracy not edge.", ""]
    if len(games) < WARM + TUNE + 60:
        return "\n".join(L + [f"Only {len(games)} games with a real half split - PENDING (HR35); nothing is graded.", ""])
    held_lo = WARM + TUNE
    best: dict[str, tuple] = {}
    tried = 0
    for k in K_GRID:
        for d in DISP_GRID:
            tried += 1
            acc = run(games, WARM, held_lo, k, d)["acc"]
            for g, tag in GROUPS:
                m = summarise(acc, PREFIX[tag])[0]
                if not math.isnan(m) and (g not in best or m < best[g][0]):
                    best[g] = (m, k, d)
    n_cnt = sum(1 for g in games if g.get("tries"))
    n_tr = sum(1 for g in games[held_lo:] if g.get("tries"))
    L += [f"Data: ESPN rugby scoreboard, {len(games)} games across Premiership, URC (Pro14), Top 14 and Champions Cup with a real "
          f"half split ({games[0]['day']} to {games[-1]['day']}); {n_cnt} also have try / penalty-goal counts that rebuild the "
          "final score (5 per try + 2 per conversion + 3 per penalty or drop goal). Later seasons have no half split in the "
          "feed and read PENDING rather than a guess.", "",
          f"Walk-forward, one matchday purged. First {WARM} games history only; next {TUNE} choose settings; **{len(games) - held_lo}** "
          f"held-out games ({n_tr} with counts). Settings tried: **{tried}** (rating shrink k x dispersion); chosen: "
          + "; ".join(f"{g}: k={best[g][1]:g}, dispersion={best[g][2]:g}" for g, _ in GROUPS if g in best) + ".", "",
          "| Event group | n events | Model log loss | Baseline log loss | Gap (base - model) | s.e. |", "|---|---|---|---|---|---|"]
    cal: list = []
    for g, tag in GROUPS:
        if g not in best:
            L.append(f"| {g} | 0 | PENDING | PENDING | | |")
            continue
        r = run(games, held_lo, len(games), best[g][1], best[g][2])
        m, b, se, n = summarise(r["acc"], PREFIX[tag])
        L.append(f"| {g} | {n} | {m:.4f} | {b:.4f} | {b - m:+.4f} | {se:.4f} |")
        if tag == "h1":
            cal = r["cal"]
    L += ["", "Calibration of P(first half over 20.5), held-out games:", "", "| Predicted | Cases | Happened |", "|---|---|---|"]
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        c = [y for p, y in cal if lo <= p < lo + 0.2 or (lo == 0.8 and p >= 1.0)]
        if c:
            L.append(f"| {lo:.1f}-{lo + 0.2:.1f} | {len(c)} | {sum(c) / len(c):.3f} |")
    L += ["", "## Reading", "",
          "- A gap above about 2 s.e. means the model beats repeating each team's own average; inside that it has not shown it.",
          "- The sample is small (a real half split exists almost only for 2014-15), so this is a first look, not proof. Conversions and "
          "drop goals feed the per-point rates; penalty tries are inside the try count.",
          "- The SportyBet market sweep (step 1 of #593), the basketball twin entry and the Control Room reader need the live feed and "
          "are a follow-up: until the sweep logs which half / try markets exist, no price is read or graded (HR35, HR59).",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def main(now: datetime | None = None) -> str:
    games = [g for g in data.load() if g.get("h1")]
    text = render(games, now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(main())
