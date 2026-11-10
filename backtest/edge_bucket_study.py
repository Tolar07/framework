"""
EDGE BUCKET STUDY (framework #533) - SHADOW, record-only. Sibling of model_sides_calibration_study.py.

Idea (arXiv 2611.10152, via the R&D bot): grading every side by the model's chance cannot tell model skill
from odds bias; bucket the same sides by the price and see where the model over- or under-performs.

Every graded board day's sides the model gives >= BAR (50%) are paper singles priced at SportyBet's last
price. They are bucketed by that price (the issue's 1.5-2.0 / 2.0-3.0 / 3.0-5.0 / 5.0+, plus <1.5; the
model's own 1/chance odds can only be <= 2.0 at 50%+, so the market price is the useful axis). Per bucket:
hit rate, mean model chance, hit-minus-chance (calibration gap), ROI of a 1-unit single.

WALK-FORWARD: the last WINDOW_DAYS graded days are split in time order; the TRAIN half picks the buckets
that looked good (ROI > 0), the TEST half is the only half judged. VALID if some bucket's TEST ROI is
above +5% and its train ROI was positive too; REJECT if no judged bucket beats +2% on the test half;
otherwise INCONCLUSIVE. Nothing here changes a pick, stake, threshold or the CLV gate.
No data -> PENDING (HR35).

    python backtest/edge_bucket_study.py -> backtest/EDGE_BUCKET_STUDY.md + data/calibrated_edge.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

OUT = ROOT / "backtest" / "EDGE_BUCKET_STUDY.md"
JSON_OUT = ROOT / "data" / "calibrated_edge.json"
BAR, WINDOW_DAYS, MIN_N = 0.50, 60, 30
VALID, REJECT = 0.05, 0.02
BUCKETS = [("<1.5", 0.0, 1.5), ("1.5-2.0", 1.5, 2.0), ("2.0-3.0", 2.0, 3.0),
           ("3.0-5.0", 3.0, 5.0), ("5.0+", 5.0, 1e9)]


def bucket_of(price: float) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= price < hi:
            return name
    return BUCKETS[-1][0]


def stats(rs: list[dict]) -> dict:
    n = len(rs)
    if not n:
        return {"n": 0}
    wins = sum(r["won"] for r in rs)
    pl = sum((r["price"] - 1) if r["won"] else -1 for r in rs)
    ch = sum(r["chance"] for r in rs) / n
    return {"n": n, "hit": wins / n, "chance": ch, "gap": wins / n - ch, "roi": pl / n}


def by_bucket(recs: list[dict]) -> dict[str, dict]:
    g = defaultdict(list)
    for r in recs:
        if r["chance"] >= BAR and r["price"]:
            g[bucket_of(r["price"])].append(r)
    return {name: stats(g.get(name, [])) for name, _, _ in BUCKETS}


def split(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Time-ordered halves of the last WINDOW_DAYS days: train = earlier half, test = later half."""
    days = sorted({r["date"] for r in recs})[-WINDOW_DAYS:]
    half = len(days) // 2
    tr, te = set(days[:half]), set(days[half:])
    return [r for r in recs if r["date"] in tr], [r for r in recs if r["date"] in te]


def analyse(recs: list[dict]) -> dict:
    train, test = split(recs)
    if not train or not test:
        return {"verdict": "PENDING", "reason": "fewer than 2 graded board days"}
    a, b = by_bucket(train), by_bucket(test)
    judged = [k for k in b if b[k]["n"] >= MIN_N]
    valid = [k for k in judged if a[k]["n"] >= MIN_N and a[k]["roi"] > 0 and b[k]["roi"] > VALID]
    if not judged:
        verdict = "PENDING"
    elif valid:
        verdict = "VALID (shadow only; promotion goes through the normal gate)"
    elif all(b[k]["roi"] <= REJECT for k in judged):
        verdict = "REJECT (no bucket shows an actionable edge on the test half)"
    else:
        verdict = "INCONCLUSIVE"
    return {"verdict": verdict, "valid_buckets": valid, "train_days": len({r["date"] for r in train}),
            "test_days": len({r["date"] for r in test}), "train": a, "test": b}


def report(recs: list[dict]) -> list[str]:
    res = analyse(recs)
    L = ["# Edge bucket study - shadow (framework #533)", "",
         f"Model sides at {BAR:.0%}+ bucketed by SportyBet's last price; train = earlier half, test = later "
         f"half of the last {WINDOW_DAYS} graded board days. Paper only; no pick, stake or threshold changes.", ""]
    if res["verdict"] == "PENDING":
        return L + ["**PENDING** - " + res.get("reason", f"no bucket has {MIN_N}+ test sides yet") + " (HR35)."]
    L += [f"Verdict: **{res['verdict']}** · train days {res['train_days']}, test days {res['test_days']}", "",
          "| Price bucket | Train n | Train ROI | Test n | Test hit | Test model chance | Test hit-chance | Test ROI |",
          "|---|---|---|---|---|---|---|---|"]
    for name, _, _ in BUCKETS:
        a, b = res["train"][name], res["test"][name]
        if not b["n"]:
            L.append(f"| {name} | {a['n']} | PENDING | 0 | PENDING | PENDING | PENDING | PENDING |")
            continue
        ta = f"{a['roi']:+.1%}" if a["n"] else "PENDING"
        L.append(f"| {name} | {a['n']} | {ta} | {b['n']} | {b['hit']:.0%} | {b['chance']:.0%} | "
                 f"{b['gap']:+.1%} | {b['roi']:+.1%} |")
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
            recs += ms.records(date, json.loads(f.read_text(encoding="utf-8")), by_day[date], floor=BAR)
    res = analyse(recs)
    OUT.write_text("\n".join(report(recs)) + "\n", encoding="utf-8")
    JSON_OUT.write_text(json.dumps({"records": len(recs), **res}, indent=1, default=str), encoding="utf-8")
    print(f"edge bucket study: {len(recs)} records -> {res['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
