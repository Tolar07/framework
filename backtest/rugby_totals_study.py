"""
RUGBY total-points walk-forward study (framework#344, record-only).

Over/Under total points is a rugby market the Elo cannot price. This replays the same ESPN games as
backtest/rugby_backtest.py in date order and asks: does a team attack/defence model predict the total better than
a flat league average? Every setting tried is counted; the best is chosen on 2014-2019 and reported on 2020+ only.

  pred = league_mean(running) + w * (home_for + away_for + home_against + away_against) / 2 - 2 * w * league_mean
  (team 'for/against' = running average of points scored/conceded over the last N games, N tried)

Score = mean absolute error (points) of the predicted total vs the real total, against the baseline "running league
mean of totals". Record only: nothing here changes a stake, a bar, a threshold or the live switch.

  python backtest/rugby_totals_study.py      writes backtest/RUGBY_TOTALS_STUDY.md
"""
from __future__ import annotations

import itertools
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_TOTALS_STUDY.md"
NS = (4, 8, 16)
WS = (0.0, 0.5, 1.0)
MIN_GAMES = 4


def replay(games: list[dict], n: int, w: float) -> list[tuple[float, float] | None]:
    """(prediction, baseline) of each game's total BEFORE it is played, None while data is thin."""
    hist = defaultdict(lambda: deque(maxlen=n))
    tot_sum, tot_n, out = 0.0, 0, []
    for g in games:
        h, a = hist[g["home"]], hist[g["away"]]
        if tot_n >= 100 and len(h) >= MIN_GAMES and len(a) >= MIN_GAMES:
            lm = tot_sum / tot_n
            hf = sum(x[0] for x in h) / len(h)
            ha = sum(x[1] for x in h) / len(h)
            af = sum(x[0] for x in a) / len(a)
            aa = sum(x[1] for x in a) / len(a)
            team = hf + aa + af + ha  # own scoring + the other side's leaking, both teams
            out.append((lm + w * (team / 2 - lm), lm))
        else:
            out.append(None)
        t = g["hs"] + g["as"]
        tot_sum, tot_n = tot_sum + t, tot_n + 1
        h.append((g["hs"], g["as"]))
        a.append((g["as"], g["hs"]))
    return out


def evaluate(games, preds, years) -> dict:
    n, e, e0 = 0, 0.0, 0.0
    for g, p in zip(games, preds):
        if p is None or not (years[0] <= g["year"] <= years[1]):
            continue
        t = g["hs"] + g["as"]
        n += 1
        e += abs(p[0] - t)
        e0 += abs(p[1] - t)
    return {"n": n, "mae": e / n if n else None, "base": e0 / n if n else None}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (rb.TUNE_YEARS[1] + 1, last)
    cache = {(n, w): replay(games, n, w) for n, w in itertools.product(NS, WS)}
    tuned = {k: evaluate(games, p, rb.TUNE_YEARS) for k, p in cache.items()}
    ok = {k: t for k, t in tuned.items() if t["n"] >= 100}
    best = min(ok, key=lambda k: ok[k]["mae"]) if ok else None
    held = evaluate(games, cache[best], test) if best else None
    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby total-points walk-forward study", "",
         f"Made {made} by `backtest/rugby_totals_study.py` (framework#344). {len(games)} games, final scores "
         f"only (ESPN). Settings tried: **{len(cache)}** (window x weight); chosen on "
         f"{rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**.", ""]
    if not held or not held["n"]:
        L.append("PENDING: not enough games to grade a total-points model.")
        return "\n".join(L) + "\n"
    L += ["| Rule (held-out years) | Games | Mean abs error (points) |", "|---|---|---|",
          f"| Baseline: running league mean total | {held['n']} | {held['base']:.2f} |",
          f"| Best on tuning years: last {best[0]} games, weight {best[1]} | {held['n']} | {held['mae']:.2f} |",
          "", "## Reading", ""]
    gain = held["base"] - held["mae"]
    if best[1] == 0.0 or gain <= 0:
        L.append(f"- Team scoring form does NOT beat the league mean on held-out games ({gain:+.2f} points): "
                 "price totals off the exchange line, not our own number.")
    else:
        L.append(f"- Team scoring form beats the league mean by {gain:.2f} points on held-out games. "
                 "A shadow candidate only; it needs the shadow record before any bar uses it.")
    L += [f"- {len(cache)} settings tried; the held-out line is the honest one.",
          "- No free historical totals lines, so no return figure: return and CLV come from the shadow record.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = rb.load()
    if len(games) < 1000:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
