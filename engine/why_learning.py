"""
WHY-WEIGHTED LEARNING — SHADOW (Architect 2026-10-28: "make learning.py able
to weight OUTPLAYED misses over UNLUCKY ones — as a shadow strategy that must
earn promotion, not a direct switch").

The live learner (engine/learning.learn) treats every loss alike. The shadow
learns from the same graded singles, but each outcome is blended with what
the match's xG deserved (engine/why_record; learning.WHY_ALPHA), so an
OUTPLAYED miss counts nearly in full and a RIGHT-UNLUCKY one about half.

WALK-FORWARD (no leakage): for every match day D of the last EVAL_DAYS, both
learners are fitted on the singles graded BEFORE D only, and score D's singles
(chance before any learned shift + each learner's shift) against what
happened: Brier, paired per pick. The why record of a single dated before D
only uses that match's own (finished) data, so nothing from D or after leaks.

PROMOTION: the shadow goes live only when, over >= MIN_DAYS match days and
>= MIN_PICKS picks, it beats the live learner's Brier by Z_PROMOTE (1.645)
standard errors. A promoted shadow that later falls behind by the same margin
is demoted. Status, numbers and the reason are written to
memory/why_learning_shadow.json every run; run_daily reads `promoted()`.
Stakes, staking, the CLV gate and ARCHITECT_SIGNOFF are not touched.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

from engine import learning
from engine import why_record as wr

ROOT = Path(__file__).parent.parent
STATUS = ROOT / "memory" / "why_learning_shadow.json"

EVAL_DAYS = 60
MIN_DAYS = 30
MIN_PICKS = 300
Z_PROMOTE = 1.645


def why_map(rows: list[dict] | None = None) -> dict:
    rows = wr.load() if rows is None else rows
    return {(r["date"], r["fixture"], r["market"]): r["deserved"]
            for r in rows if r.get("deserved") is not None}


def _p(model: dict, s: dict) -> float:
    c = float(s.get("chance_raw", s["chance"]))
    return min(0.999, max(0.001, c + learning.shift(model, s.get("market"), s.get("league") or "?")))


def evaluate(ledger_dir: Path = wr.LEDGER_DIR,
             today: str | None = None, why: dict | None = None,
             docs: list | None = None) -> dict:
    today = today or date.today().isoformat()
    docs = learning.load_docs(ledger_dir) if docs is None else docs
    why = why_map() if why is None else why
    start = (date.fromisoformat(today) - timedelta(days=EVAL_DAYS)).isoformat()
    diffs, days, b_live, b_shadow = [], 0, 0.0, 0.0
    for doc in docs:
        d = doc["date"]
        if not (start <= d < today):
            continue
        singles = [s for s in doc.get("singles", [])
                   if s.get("result") in ("won", "lost") and s.get("chance") is not None]
        if not singles:
            continue
        live = learning.learn(ledger_dir, today=d, docs=docs)
        shadow = learning.learn(ledger_dir, today=d, why=why, docs=docs)
        days += 1
        for s in singles:
            y = 1.0 if s["result"] == "won" else 0.0
            bl, bs = (_p(live, s) - y) ** 2, (_p(shadow, s) - y) ** 2
            b_live += bl
            b_shadow += bs
            diffs.append(bl - bs)               # > 0: the shadow was closer
    n = len(diffs)
    mean = sum(diffs) / n if n else 0.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in diffs) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n and sd > 0 else 0.0
    z = mean / se if se > 0 else 0.0
    return {"evaluated_at": today, "days": days, "picks": n,
            "brier_live": round(b_live / n, 5) if n else None,
            "brier_shadow": round(b_shadow / n, 5) if n else None,
            "gain_per_pick": round(mean, 6), "z": round(z, 2)}


def decide(res: dict, prev: dict | None = None) -> dict:
    was = (prev or {}).get("status", "shadow")
    enough = res["days"] >= MIN_DAYS and res["picks"] >= MIN_PICKS
    if was != "promoted" and enough and res["z"] >= Z_PROMOTE:
        status, why = "promoted", f"beat the live learner by z {res['z']} over {res['picks']} unseen picks"
    elif was == "promoted" and enough and res["z"] <= -Z_PROMOTE:
        status, why = "shadow", f"demoted: fell behind the live learner by z {res['z']}"
    elif not enough:
        status, why = was, (f"shadow: {res['days']}/{MIN_DAYS} days, {res['picks']}/{MIN_PICKS} picks "
                            f"before it can be judged")
    else:
        status, why = was, f"{was}: z {res['z']} (needs {Z_PROMOTE} to change)"
    out = dict(res)
    out.update({"status": status, "why": why, "alpha": learning.WHY_ALPHA})
    if status != was:
        out["changed_at"] = res["evaluated_at"]
    elif prev and prev.get("changed_at"):
        out["changed_at"] = prev["changed_at"]
    return out


def load(path: Path = STATUS) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def promoted(path: Path = STATUS) -> bool:
    return load(path).get("status") == "promoted"


def run(path: Path = STATUS, today: str | None = None) -> dict:
    out = decide(evaluate(today=today), load(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def line(st: dict) -> str:
    if not st:
        return "Why-weighted learning (shadow): not evaluated yet"
    b = (f"Brier live {st['brier_live']} v shadow {st['brier_shadow']}, "
         if st.get("brier_live") is not None else "")
    return f"Why-weighted learning ({st['status']}): {b}{st['why']}"


if __name__ == "__main__":
    print(line(run()))
