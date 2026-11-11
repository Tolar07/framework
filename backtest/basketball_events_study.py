"""
Walk-forward study of the basketball player-event model (framework #558). RECORD-ONLY: writes
backtest/BASKETBALL_EVENTS_STUDY.md and nothing else.

    python backtest/basketball_events_study.py

Each player-game of the NBA log is predicted from games dated at least two days earlier (a purge gap of one
matchday: nothing from the game's own night or the night before), by engine/basketball_events.expected, and scored
against the baseline every prediction must beat: the player's last-10-games average. Two scores per stat:
- MAE of the expected value (all scored games);
- log loss of the Over / Under chance at the half line nearest the baseline (the line a book would post), on the
  LATER half of the scored games. The negative-binomial spread (variance / mean) is fitted on the EARLIER half only,
  for the model and the baseline alike, so the scored half is out-of-sample for it too.
A stat is published (BASKET_PUBLISH) only when the model beats the baseline on BOTH scores, with at least MIN_N
scored games. Things tried: one model, one set of constants chosen before the run, 4 stats = 4 tests (stated, so
the result is read with that in mind: the deflated-Sharpe habit).
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import basketball_events as be  # noqa: E402

OUT = ROOT / "backtest" / "BASKETBALL_EVENTS_STUDY.md"
MIN_N = 200
MIN_EXPECTED = 10.0       # only players in the rotation are scored


def walk(rows: list[dict]) -> list[dict]:
    """Every scored player-game: {stat: (model mean, baseline mean, actual)} plus date."""
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(r["d"], []).append(r)
    out = []
    for d in sorted(by_date):
        cutoff = (date.fromisoformat(d) - timedelta(days=2)).isoformat()
        past = [r for r in rows if r["d"] <= cutoff]
        if len({r["g"] for r in past}) < 20:
            continue
        lg = be.league_rates(past)
        hist = be.by_player(past)
        for r in by_date[d]:
            g = hist.get(r["p"], [])
            e = be.expected(g, lg)
            if e is None or e["min"] < MIN_EXPECTED:
                continue
            out.append({"d": d, "p": r["p"], **{s: (e[s], be.baseline(g, s), r[s]) for s in be.STATS}})
    return out


def fit_disp(rows: list[dict], stat: str) -> float:
    """Variance-to-mean ratio of (actual - model mean), at least 1 (Poisson floor)."""
    res = [(a - m) ** 2 for m, _b, a in (x[stat] for x in rows)]
    means = [m for m, _b, _a in (x[stat] for x in rows)]
    return max(1.0, sum(res) / max(sum(means), 1e-9))


def logloss(rows: list[dict], stat: str, which: int, disp: float) -> tuple[float, list[tuple[float, int]]]:
    """Log loss of Over at the half line nearest the baseline; which 0 = model mean, 1 = baseline mean."""
    ll, pairs = 0.0, []
    for x in rows:
        m, b, a = x[stat]
        line = math.floor(b) + 0.5
        p = be.over_under((m, b)[which], line, disp)["over"]
        p = min(max(p, 1e-4), 1 - 1e-4)
        y = int(a > line)
        ll -= math.log(p if y else 1 - p)
        pairs.append((p, y))
    return ll / len(rows), pairs


def buckets(pairs: list[tuple[float, int]]) -> list[tuple[str, int, float, float]]:
    out = []
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        sub = [(p, y) for p, y in pairs if lo <= p < lo + 0.2 or (lo == 0.8 and p == 1.0)]
        if sub:
            out.append((f"{lo:.1f}-{lo + 0.2:.1f}", len(sub), sum(p for p, _ in sub) / len(sub),
                        sum(y for _, y in sub) / len(sub)))
    return out


def study(rows: list[dict]) -> dict:
    scored = walk(rows)
    scored.sort(key=lambda x: x["d"])
    half = len(scored) // 2
    fit, test = scored[:half], scored[half:]
    res = {"n_scored": len(scored), "n_test": len(test), "stats": {}}
    for s in be.STATS:
        if len(test) < 20:
            res["stats"][s] = {"n": len(test), "publish": False, "why": "PENDING: too few games scored"}
            continue
        disp = fit_disp(fit, s)
        mae_m = sum(abs(m - a) for m, _b, a in (x[s] for x in scored)) / len(scored)
        mae_b = sum(abs(b - a) for _m, b, a in (x[s] for x in scored)) / len(scored)
        ll_m, pairs = logloss(test, s, 0, disp)
        ll_b, _ = logloss(test, s, 1, disp)
        res["stats"][s] = {"n": len(test), "disp": round(disp, 2), "mae_model": mae_m, "mae_base": mae_b,
                           "ll_model": ll_m, "ll_base": ll_b, "buckets": buckets(pairs),
                           "publish": bool(len(test) >= MIN_N and mae_m < mae_b and ll_m < ll_b)}
    return res


def render(res: dict, today: date) -> str:
    pub = [s for s, v in res["stats"].items() if v.get("publish")]
    L = [f"# Basketball player events: walk-forward study (framework #558) - {today.isoformat()}", "",
         f"Scored player-games (rotation players, expected minutes >= {MIN_EXPECTED:.0f}): {res['n_scored']}; "
         f"the later half ({res['n_test']}) is out-of-sample for the spread fit and the log loss.",
         f"Baseline: the player's last-10-games average. Tests run: 4 (one model, constants fixed before the run).",
         f"Published only if the model beats the baseline on MAE and on log loss with at least {MIN_N} games.", "",
         "| stat | games | MAE model | MAE last-10 | log loss model | log loss last-10 | spread | published |",
         "|---|---|---|---|---|---|---|---|"]
    for s, v in res["stats"].items():
        if "mae_model" not in v:
            L.append(f"| {be.LABEL[s]} | {v['n']} | PENDING | | | | | no |")
            continue
        L.append(f"| {be.LABEL[s]} | {v['n']} | {v['mae_model']:.3f} | {v['mae_base']:.3f} | {v['ll_model']:.4f} | "
                 f"{v['ll_base']:.4f} | {v['disp']} | {'YES' if v['publish'] else 'no'} |")
    L += ["", "Calibration of the model's Over chance at the baseline line (later half):", ""]
    for s, v in res["stats"].items():
        if v.get("buckets"):
            L.append(f"- {be.LABEL[s]}: " + "; ".join(f"{b} n={n} said {p:.2f} got {y:.2f}" for b, n, p, y in v["buckets"]))
    L += ["", "Machine-read lines (monitor/basketball_events_run.py):", "",
          f"BASKET_PUBLISH = [{', '.join(repr(s) for s in pub)}]",
          "DISP = {" + ", ".join(f"{s!r}: {v['disp']}" for s, v in res["stats"].items() if "disp" in v) + "}", ""]
    return "\n".join(L)


def main() -> int:
    rows = be.load_stats()
    if not rows:
        print("no player-stat log yet: PENDING")
        return 0
    res = study(rows)
    OUT.write_text(render(res, date.today()), encoding="utf-8", newline="\n")
    print(render(res, date.today()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
