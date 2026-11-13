"""
Volleyball events study (framework #591, Event models #12; RECORD ONLY). Writes backtest/VOLLEYBALL_EVENTS_STUDY.md.

Question: does the set ladder + points model in engine/volleyball_events.py (board Elo win chance -> best-of-5 score
ladder with set momentum; total points = ladder chance of 3/4/5 sets mixed with earlier point totals for that many sets)
beat the plain frequency of earlier matches at (a) the exact set score, (b) sets over 3.5 / 4.5 and home/away -1.5 sets,
(c) total points over five lines taken from the earlier totals' percentiles?

Data: data/volleyball_sets.py (ESPN NCAA women's, 2016-2025 falls; college, not the pro leagues). No free historical
set-market prices exist, so this measures accuracy, not return.

Walk-forward, one-matchday purge: a match on day D is predicted from matches dated BEFORE D-1 only (Elo and the
frequencies both). The momentum m (0 / 0.1 / 0.15 / 0.2) is counted and picked on matches before SPLIT; only matches from
SPLIT on are reported. Baseline = earlier frequency (+ smoothing). Nothing here changes a pick, stake or threshold.

  python backtest/volleyball_events_study.py
"""
from __future__ import annotations

import math
import sys
from bisect import insort
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import volleyball_sets as vs  # noqa: E402
from engine import volleyball_events as ve  # noqa: E402

OUT = ROOT / "backtest" / "VOLLEYBALL_EVENTS_STUDY.md"
SPLIT = "2021-01-01"
MOMENTA = (0.0, 0.10, 0.15, 0.20)
ELO_K, ELO_START, MIN_GAMES = 24.0, 1500.0, 8
EPS = 1e-4
SETMKT = {"Sets over 3.5": ("3-1", "1-3", "3-2", "2-3"), "Sets over 4.5": ("3-2", "2-3"),
          "Home -1.5 sets": ("3-0", "3-1"), "Away -1.5 sets": ("0-3", "1-3")}


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def run(rows: list[dict], momenta: tuple[float, ...] = MOMENTA, min_hist: int = 300) -> dict:
    """Walk-forward. Per momentum: one dict per scored match with model and baseline log losses."""
    elo: dict[str, float] = {}
    cnt: dict[str, int] = {}
    score_n = {k: 0 for k in ve.SCORES}
    n_done = 0
    hist: dict[int, list[int]] = {3: [], 4: [], 5: []}
    ptr = 0
    pend: list[tuple[date, dict]] = []
    res = {m: [] for m in momenta}
    for x in rows:
        day = date.fromisoformat(x["day"])
        cutoff = day - timedelta(days=1)
        while ptr < len(pend) and pend[ptr][0] < cutoff:          # only matches dated before D-1 are visible
            _, g = pend[ptr]
            h, a = g["home"], g["away"]
            rh, ra = elo.get(h, ELO_START), elo.get(a, ELO_START)
            e = 1 / (1 + 10 ** ((ra - rh) / 400))
            d = ELO_K * ((1.0 if g["hs"] > g["as"] else 0.0) - e)
            elo[h], elo[a] = rh + d, ra - d
            cnt[h], cnt[a] = cnt.get(h, 0) + 1, cnt.get(a, 0) + 1
            score_n[f"{g['hs']}-{g['as']}"] += 1
            n_done += 1
            insort(hist[len(g["sets"])], sum(p + q for p, q in g["sets"]))
            ptr += 1
        h, a = x["home"], x["away"]
        rated = cnt.get(h, 0) >= MIN_GAMES and cnt.get(a, 0) >= MIN_GAMES
        pend.append((day, x))
        if not rated or n_done < min_hist or any(len(v) < ve.MIN_PER_COUNT for v in hist.values()):
            continue
        p = 1 / (1 + 10 ** ((elo.get(a, ELO_START) - elo.get(h, ELO_START)) / 400))
        key = f"{x['hs']}-{x['as']}"
        tot = sum(s + t for s, t in x["sets"])
        lines = ve.point_lines(hist)
        flat = {k: (v + 1) / (n_done + len(ve.SCORES)) for k, v in score_n.items()}
        for m in momenta:
            pr = ve.predict(p, m, hist)
            r = {"day": x["day"], "sc_m": -math.log(max(pr["score"][key], EPS)), "sc_b": -math.log(flat[key])}
            sm = sb = 0.0
            for name, cells in SETMKT.items():
                y = int(key in cells)
                pm = {"Sets over 3.5": pr["sets_over"]["3.5"], "Sets over 4.5": pr["sets_over"]["4.5"],
                      "Home -1.5 sets": pr["handicap_cover"]["home -1.5"], "Away -1.5 sets": pr["handicap_cover"]["away -1.5"]}[name]
                sm += ll(pm, y)
                sb += ll(sum(flat[c] for c in cells), y)
            r["set_m"], r["set_b"] = sm / len(SETMKT), sb / len(SETMKT)
            pool = sorted(t for v in hist.values() for t in v)
            pm_ = pb_ = 0.0
            for ln in lines:
                y = int(tot > ln)
                pm_ += ll(pr["points_over"][str(ln)], y)
                pb_ += ll(ve.over(pool, ln), y)
                r.setdefault("cal", []).append((pr["points_over"][str(ln)], y))
            r["pt_m"], r["pt_b"] = pm_ / len(lines), pb_ / len(lines)
            res[m].append(r)
    return res


def summarise(rows: list[dict], a: str, b: str) -> tuple[float, float, float, int]:
    """(mean a, mean b, standard error of the mean of b - a, n)."""
    n = len(rows)
    if not n:
        return 0.0, 0.0, 0.0, 0
    d = [r[b] - r[a] for r in rows]
    mu = sum(d) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in d) / max(n - 1, 1))
    return sum(r[a] for r in rows) / n, sum(r[b] for r in rows) / n, sd / math.sqrt(n), n


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Volleyball events study (set totals, set handicap, total points)", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/volleyball_events_study.py` (framework #591). Record only, a shadow; "
         "NCAA women's data (college, not the pro leagues); no price in the source, so accuracy not edge.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python -c \"from data import volleyball_sets as v; v.load()\"`).", ""])
    res = run(rows)
    tune = {m: [r for r in v if r["day"] < SPLIT] for m, v in res.items()}
    if not any(tune.values()):
        return "\n".join(L + ["No tuning-period match with enough history - PENDING.", ""])
    best = min(MOMENTA, key=lambda m: summarise(tune[m], "sc_m", "sc_b")[0] if tune[m] else 9e9)
    held = [r for r in res[best] if r["day"] >= SPLIT]
    L += [f"Settings tried: **{len(MOMENTA)}** (set momentum {', '.join(str(m) for m in MOMENTA)}); chosen on matches before "
          f"{SPLIT}: **{best}**. Held-out matches from {SPLIT}: **{len(held)}**.", "",
          "| Event | Model log loss | Earlier-frequency log loss | Gain (base - model) | s.e. |", "|---|---|---|---|---|"]
    for name, a, b in (("Exact set score", "sc_m", "sc_b"), ("Set markets (over 3.5/4.5, -1.5 home/away)", "set_m", "set_b"),
                       ("Total points over, 5 lines", "pt_m", "pt_b")):
        mu, bs, sem, _ = summarise(held, a, b)
        L.append(f"| {name} | {mu:.4f} | {bs:.4f} | {bs - mu:+.4f} | {sem:.4f} |")
    L += ["", "Calibration of the total-points over chance (held-out, chosen momentum):", "",
          "| Predicted | Cases | Happened |", "|---|---|---|"]
    cal = [c for r in held for c in r.get("cal", [])]
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        c = [y for pm, y in cal if lo <= pm < lo + 0.2 or (lo == 0.8 and pm >= 1.0)]
        if c:
            L.append(f"| {lo:.1f}-{lo + 0.2:.1f} | {len(c)} | {sum(c) / len(c):.3f} |")
    L += ["", "## Reading", "",
          "- A positive gain means the model beats repeating how earlier matches finished; within about 2 s.e. of zero is no proof.",
          "- Points are mixed by set count only; a team that plays long, close sets is not told apart (a known simplification).",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def main(now: datetime | None = None) -> str:
    text = render(vs.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(main())
