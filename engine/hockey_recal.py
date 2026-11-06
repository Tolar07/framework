"""
ICE HOCKEY NIGHTLY BLEND CHECK (standing order 50, "nightly retrain on the Oracle clock"; RECORD ONLY).

The hockey board freezes, for every side of every game, the goals model's chance (`model`) and the
exchange's de-vigged fair chance (`fair`) at the first look. Once the game is graded (`won`) each side is
a yes/no outcome. Every night this file asks, on that graded record only:

  Does a blend  w x model + (1 - w) x exchange fair  predict better than the exchange alone?

Method (walk-forward, nothing fitted on the games it is scored on): sides sorted by kick-off; the
newest ~20% (whole days) is the HOLDOUT, the rest the FIT set; w is the best of 0.0..1.0 in 0.1 steps
on the fit set (11 tries, all logged); the holdout Brier of w=0 (exchange), w=1 (model) and the fitted
blend are written to memory/hockey_retrain_log.jsonl. Too few sides = PENDING (HR35), never a guess.

It changes NOTHING: no pick rule, stake, threshold or live switch reads it. If the blend keeps winning
the Architect can decide whether to use it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

LOG = ROOT / "memory" / "hockey_retrain_log.jsonl"
MIN_FIT = 150
MIN_HOLDOUT = 50
HOLDOUT_SHARE = 0.2
WEIGHTS = [i / 10 for i in range(11)]


def sides_of(docs: list[tuple[str, dict]]) -> list[dict]:
    """Graded sides that have BOTH a model chance and an exchange fair chance at the first look."""
    out = []
    for day, doc in docs:
        for g in (doc.get("games") or {}).values():
            for key, s in (g.get("sides") or {}).items():
                f = s.get("first") or {}
                if s.get("won") is None or f.get("model") is None or f.get("fair") is None:
                    continue
                out.append({"day": day, "key": key, "model": f["model"], "fair": f["fair"], "won": int(bool(s["won"]))})
    return sorted(out, key=lambda r: r["day"])


def brier(rows: list[dict], w: float) -> float:
    return sum((w * r["model"] + (1 - w) * r["fair"] - r["won"]) ** 2 for r in rows) / len(rows)


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Newest ~HOLDOUT_SHARE of the rows, cut on a day boundary, is the holdout."""
    cut = rows[int(len(rows) * (1 - HOLDOUT_SHARE))]["day"]
    return [r for r in rows if r["day"] < cut], [r for r in rows if r["day"] >= cut]


def check(rows: list[dict]) -> dict:
    if len(rows) < MIN_FIT + MIN_HOLDOUT:
        return {"status": "PENDING", "sides": len(rows), "need": MIN_FIT + MIN_HOLDOUT}
    fit, hold = split(rows)
    if len(fit) < MIN_FIT or len(hold) < MIN_HOLDOUT:
        return {"status": "PENDING", "sides": len(rows), "fit": len(fit), "holdout": len(hold)}
    tries = {w: brier(fit, w) for w in WEIGHTS}
    best = min(tries, key=lambda w: tries[w])
    b_ex, b_mod, b_blend = brier(hold, 0.0), brier(hold, 1.0), brier(hold, best)
    return {"status": "OK", "fit": len(fit), "holdout": len(hold), "tries": len(tries), "w": best,
            "fit_brier_by_w": {str(w): round(v, 5) for w, v in tries.items()},
            "holdout_brier": {"exchange": round(b_ex, 5), "model": round(b_mod, 5), "blend": round(b_blend, 5)},
            "blend_beats_exchange": b_blend < b_ex}


def run(docs: list[tuple[str, dict]] | None = None, log: Path = LOG, now: datetime | None = None) -> dict:
    if docs is None:
        from engine import ice_hockey as ih
        docs = ih.load_all()
    res = check(sides_of(docs))
    res["at"] = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%MZ")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(res) + "\n")
    return res


if __name__ == "__main__":
    print(json.dumps(run()))
