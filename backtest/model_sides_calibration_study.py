"""
MODEL SIDES CALIBRATION STUDY (framework #377) - SHADOW, record-only.

backtest/model_sides_study.py showed the model over-rates Unders and under-rates Overs. Would a
per-side calibrator fix it? Every side of every market on every graded board day (all chances, not
only 50%+) is one record: the model's chance, SportyBet's last price, won 1/0. Groups are
(market, side-kind), e.g. "Over/Under goals | Under N".

WALK-FORWARD, one day at a time: for each test day D the calibrator for a group is fitted ONLY on
that group's records from the TRAIN_DAYS days before D (Platt scaling: logit(p') = a + b*logit(p),
ridge-pulled toward a=0,b=1, so a thin group stays near the raw chance). Groups with fewer than
MIN_N training records are left raw. Then on D: Brier of raw vs calibrated chance, and a 1-unit
paper single on every side whose chance is >= BAR, priced at SportyBet's price (raw chance picks vs
calibrated chance picks). Verdict follows the issue: reject if calibration worsens Brier, or its
ROI is below raw ROI by more than 2 points.

Nothing here changes a pick, stake or threshold. No data -> PENDING (HR35).

    python backtest/model_sides_calibration_study.py   -> backtest/MODEL_SIDES_CALIBRATION_STUDY.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from math import exp, log
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

OUT = ROOT / "backtest" / "MODEL_SIDES_CALIBRATION_STUDY.md"
TRAIN_DAYS, MIN_N, RIDGE, BAR, ROI_TOL = 60, 50, 5.0, 0.50, 0.02


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return log(p / (1 - p))


def _sig(z: float) -> float:
    return 1 / (1 + exp(-max(min(z, 30), -30)))


def fit_platt(chances: list[float], won: list[int]) -> tuple[float, float]:
    """Ridge Platt scaling by Newton steps; the ridge pulls (a, b) toward (0, 1)."""
    a, b = 0.0, 1.0
    xs = [_logit(c) for c in chances]
    for _ in range(25):
        ga, gb, haa, hab, hbb = RIDGE * a, RIDGE * (b - 1), RIDGE, 0.0, RIDGE
        for x, y in zip(xs, won):
            p = _sig(a + b * x)
            r, w = p - y, p * (1 - p)
            ga += r
            gb += r * x
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da, db = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-8:
            break
    return a, b


def group_of(rec: dict) -> str:
    return f"{rec['market']} | {re.sub(r'[0-9.:+-]+', 'N', rec['side']).replace('(N)', '').strip()}"


def walk_forward(recs: list[dict], train_days: int = TRAIN_DAYS, min_n: int = MIN_N) -> list[dict]:
    """Each record gets 'cal' = its chance calibrated from earlier days only (raw if the group is thin)."""
    days = sorted({r["date"] for r in recs})
    by_day = defaultdict(list)
    for r in recs:
        by_day[r["date"]].append(r)
    out = []
    for i, d in enumerate(days):
        train = defaultdict(list)
        for pd_ in days[max(0, i - train_days):i]:
            for r in by_day[pd_]:
                train[group_of(r)].append(r)
        params = {g: fit_platt([x["chance"] for x in rs], [x["won"] for x in rs])
                  for g, rs in train.items() if len(rs) >= min_n}
        for r in by_day[d]:
            g = group_of(r)
            if g in params:
                a, b = params[g]
                cal, used = _sig(a + b * _logit(r["chance"])), True
            else:
                cal, used = r["chance"], False
            out.append({**r, "group": g, "cal": cal, "used": used})
    return out


def score(recs: list[dict]) -> dict:
    n = len(recs)
    if not n:
        return {"n": 0}

    def brier(k):
        return sum((r[k] - r["won"]) ** 2 for r in recs) / n

    def roi(k):
        picks = [r for r in recs if r[k] >= BAR]
        pl = sum((r["price"] - 1) if r["won"] else -1 for r in picks)
        return len(picks), (pl / len(picks) if picks else 0.0)
    (nr, rr), (nc, rc) = roi("chance"), roi("cal")
    return {"n": n, "brier_raw": brier("chance"), "brier_cal": brier("cal"),
            "picks_raw": nr, "roi_raw": rr, "picks_cal": nc, "roi_cal": rc}


def verdict(s: dict) -> str:
    if not s.get("n"):
        return "PENDING"
    if s["brier_cal"] >= s["brier_raw"]:
        return "REJECT (Brier not better)"
    if s["roi_cal"] < s["roi_raw"] - ROI_TOL:
        return "REJECT (ROI worse by more than 2 pts)"
    return "KEEP AS SHADOW (promotion goes through the normal gate)"


def report(recs: list[dict]) -> list[str]:
    cal = [r for r in walk_forward(recs) if r["used"]]
    L = ["# Model sides calibration study - shadow (framework #377)", "",
         f"Walk-forward Platt calibration per (market, side), trained on the {TRAIN_DAYS} days before each "
         f"test day, groups with {MIN_N}+ training records. Paper only; no pick, stake or threshold changes.", ""]
    if not cal:
        return L + ["**PENDING** - no graded board days with enough history to calibrate (HR35)."]
    s = score(cal)
    L += [f"Calibrated records: {s['n']} · verdict: **{verdict(s)}**", "",
          "| | Brier (lower better) | Picks at 50%+ | ROI per pick |", "|---|---|---|---|",
          f"| raw model | {s['brier_raw']:.4f} | {s['picks_raw']} | {s['roi_raw']:+.1%} |",
          f"| calibrated | {s['brier_cal']:.4f} | {s['picks_cal']} | {s['roi_cal']:+.1%} |", "",
          "## By group", "",
          "| Group | Records | Brier raw | Brier cal | ROI raw | ROI cal | Verdict |", "|---|---|---|---|---|---|---|"]
    groups = defaultdict(list)
    for r in cal:
        groups[r["group"]].append(r)
    for g, rs in sorted(groups.items(), key=lambda t: -len(t[1])):
        if len(rs) >= 30:
            x = score(rs)
            L.append(f"| {g} | {x['n']} | {x['brier_raw']:.4f} | {x['brier_cal']:.4f} | {x['roi_raw']:+.1%} | "
                     f"{x['roi_cal']:+.1%} | {verdict(x)} |")
    return L


def main() -> int:
    import model_sides_study as ms
    from engine import universe as uv
    by_day = defaultdict(list)
    for g in uv.load_graded():
        if g.get("sport") == "football" and g.get("result") and "srl" not in (g["home"] + g["away"]).lower():
            by_day[(g.get("ko") or "")[:10]].append(g)
    recs = []
    for f in sorted(ms.PICKS_DIR.glob("picks_????-??-??.json")):
        date = f.stem.split("_")[1]
        if by_day.get(date):
            recs += ms.records(date, json.loads(f.read_text(encoding="utf-8")), by_day[date], floor=0.0)
    OUT.write_text("\n".join(report(recs)) + "\n", encoding="utf-8")
    print(f"model sides calibration study: {len(recs)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
