"""
NFL margin-distribution walk-forward study (framework#384, record-only; refs #339).

A win chance says nothing about a -10.5 handicap. This prices "home wins by more than k" for every half-point k from
-20.5 to 20.5 from the CLOSING spread (nflverse games.csv: final scores + spread_line, free), three ways, replayed in
date order so each game only sees earlier games:

  A  Normal(mean = spread, sd 13.45 fixed)              the common textbook shape, no key numbers
  B  Normal(mean = spread, sd = running sd of past misses)
  C  empirical: past margins of games with the same rounded spread (clipped to +-14), shrunk to B with weight W
     (W = pseudo-games), so the spikes at 3 and 7 (key numbers) are learned, not assumed.

Score = mean log loss over all events, and over the key-number lines (+-2.5, +-3.5, +-6.5, +-7.5) alone. Every
setting tried (W) is counted; the best is chosen on 2006-2015 and reported on 2016+ only. No free alternate-line
prices exist, so there is no return figure: return and CLV come from the shadow record (HR35: PENDING until then).
Record only: nothing here changes a stake, bar, threshold or live switch.

  python backtest/nfl_margin_study.py      writes backtest/NFL_MARGIN_STUDY.md
"""
from __future__ import annotations

import csv
import io
import math
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "NFL_MARGIN_STUDY.md"
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
TUNE = (2006, 2015)
WARMUP = 500
WS = (10.0, 20.0, 40.0)
FIXED_SD = 13.45
LINES = [i + 0.5 for i in range(-21, 21)]
KEY_LINES = {-7.5, -6.5, -3.5, -2.5, 2.5, 3.5, 6.5, 7.5}
EPS = 1e-4


def load(text: str | None = None) -> list[dict]:
    if text is None:
        req = urllib.request.Request(URL, headers={"User-Agent": "olp-xdv-backtest"})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
            text = r.read().decode("utf-8")
    games = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            season = int(row["season"])
            m = int(row["home_score"]) - int(row["away_score"])
            sp = float(row["spread_line"])
        except (KeyError, ValueError):
            continue
        games.append({"season": season, "day": row["gameday"], "home": row["home_team"], "margin": m, "spread": sp})
    games.sort(key=lambda g: (g["day"], g["home"]))
    return games


def ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bucket(spread: float) -> int:
    return max(-14, min(14, int(round(spread))))


def _clip(p: float) -> float:
    return min(1 - EPS, max(EPS, p))


def replay(games: list[dict], ws=WS) -> list[dict | None]:
    """Per game BEFORE it is seen: {line: (pA, pB, {W: pC})} for P(home margin > line); None while data is thin."""
    by_bucket: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    n_bucket: dict[int, int] = defaultdict(int)
    ss, n, out = 0.0, 0, []
    for g in games:
        if n < WARMUP:
            out.append(None)
        else:
            sd = math.sqrt(ss / n)
            b = bucket(g["spread"])
            cnt = by_bucket[b]
            nb = n_bucket[b]
            pred = {}
            for k in LINES:
                pa = _clip(1 - ncdf((k - g["spread"]) / FIXED_SD))
                pb = _clip(1 - ncdf((k - g["spread"]) / sd))
                gt = sum(c for m, c in cnt.items() if m > k)
                pred[k] = (pa, pb, {w: _clip((gt + w * pb) / (nb + w)) for w in ws})
            out.append(pred)
        r = g["margin"] - g["spread"]
        ss, n = ss + r * r, n + 1
        by_bucket[bucket(g["spread"])][g["margin"]] += 1
        n_bucket[bucket(g["spread"])] += 1
    return out


def evaluate(games, preds, years, w) -> dict:
    """Mean log loss of A, B, C(w) over all lines and over the key lines alone."""
    tot = {"all": [0.0, 0.0, 0.0], "key": [0.0, 0.0, 0.0]}
    cnt = {"all": 0, "key": 0}
    games_n = 0
    for g, p in zip(games, preds):
        if p is None or not (years[0] <= g["season"] <= years[1]):
            continue
        games_n += 1
        for k, (pa, pb, pc) in p.items():
            y = 1.0 if g["margin"] > k else 0.0
            ll = [-math.log(q if y else 1 - q) for q in (pa, pb, pc[w])]
            for grp in (("all", "key") if k in KEY_LINES else ("all",)):
                cnt[grp] += 1
                for i in range(3):
                    tot[grp][i] += ll[i]
    res = {"n": games_n}
    for grp in ("all", "key"):
        res[grp] = [t / cnt[grp] for t in tot[grp]] if cnt[grp] else None
    return res


def key_freq(games, years) -> dict:
    """Held-out share of games decided by exactly 3 / 7 / 10 points, vs the Normal shape's share."""
    sel = [g for g in games if years[0] <= g["season"] <= years[1]]
    n = len(sel)
    if not n:
        return {"n": 0}
    sd = math.sqrt(sum((g["margin"] - g["spread"]) ** 2 for g in sel) / n)
    out = {"n": n}
    for m in (3, 7, 10):
        emp = sum(1 for g in sel if abs(g["margin"]) == m) / n
        nor = sum(ncdf((m + .5 - g["spread"]) / sd) - ncdf((m - .5 - g["spread"]) / sd) +
                  ncdf((-m + .5 - g["spread"]) / sd) - ncdf((-m - .5 - g["spread"]) / sd) for g in sel) / n
        out[m] = (emp, nor)
    return out


def run(games: list[dict]) -> str:
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    last = max((g["season"] for g in games), default=0)
    test = (TUNE[1] + 1, last)
    L = ["# NFL margin-distribution walk-forward study", "",
         f"Made {made} by `backtest/nfl_margin_study.py` (framework#384, refs #339). {len(games)} NFL games with a "
         f"closing spread (nflverse). Settings tried: **{len(WS)}** (shrink weight W); chosen on {TUNE[0]}-{TUNE[1]}, "
         f"reported on **{test[0]}-{test[1]} only**.", ""]
    if len(games) < 2000 or test[0] > test[1]:
        L.append("PENDING: not enough games to grade a margin model.")
        return "\n".join(L) + "\n"
    preds = replay(games)
    tuned = {w: evaluate(games, preds, TUNE, w) for w in WS}
    ok = {w: t for w, t in tuned.items() if t["n"] and t["all"]}
    if not ok:
        L.append("PENDING: no tuning data.")
        return "\n".join(L) + "\n"
    best = min(ok, key=lambda w: ok[w]["all"][2])
    held = evaluate(games, preds, test, best)
    if not held["n"]:
        L.append("PENDING: no held-out games.")
        return "\n".join(L) + "\n"
    L += ["Log loss of 'home wins by more than k' over every half-point line -20.5..20.5 (lower is better):", "",
          f"| Model (held-out {test[0]}-{test[1]}, {held['n']} games) | All lines | Key-number lines (+-2.5/3.5/6.5/7.5) |",
          "|---|---|---|"]
    names = ["A Normal, sd 13.45 fixed", "B Normal, running sd", f"C empirical by spread, W={best:g}"]
    for i, nm in enumerate(names):
        L.append(f"| {nm} | {held['all'][i]:.4f} | {held['key'][i]:.4f} |")
    kf = key_freq(games, test)
    L += ["", f"Share of games decided by exactly N points, held-out ({kf['n']} games), real vs Normal shape:", ""]
    L += [f"- {m} pts: real {kf[m][0]*100:.1f}% vs Normal {kf[m][1]*100:.1f}%" for m in (3, 7, 10)]
    L += ["", "## Reading", ""]
    ga, gk = held["all"][1] - held["all"][2], held["key"][1] - held["key"][2]
    if gk > 0:
        L.append(f"- The empirical shape beats the Normal on the key-number lines by {gk:.4f} log loss held-out "
                 f"({ga:+.4f} over all lines): price NFL handicaps and bands near 3 and 7 from it, not a Normal. "
                 "A shadow candidate only; it needs the shadow record before any bar uses it.")
    else:
        L.append(f"- The empirical shape does NOT beat the Normal on the key-number lines ({gk:+.4f}): keep the "
                 "Normal and the exchange line.")
    L += [f"- {len(WS)} settings tried; the held-out line is the honest one.",
          "- Means are the closing spread, i.e. the market's own number; this grades the SHAPE around it, not a "
          "better mean. No free alternate-line prices, so no return figure (PENDING, HR35).",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 2000:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
