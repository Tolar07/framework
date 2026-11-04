"""
SOFT-CLOSE SHADOW (issue #251, research hypothesis H003). RECORDED ONLY.

H003 was accepted by research/runner.py: SportyBet's closing Over 2.5 price (margin removed) knows
something the model's Over 2.5 chance doesn't. This module keeps that lean as a SHADOW next to the
live model, never in front of it:

    shadow = sigmoid(logit(model) + coef * (gap - mu) / sd)       gap = soft close chance - model chance

mu / sd / coef are fitted on every earlier graded fixture (engine/walkforward.fit_offset, the same
ridge fit the research harness used). Each day is scored walk-forward, so the Brier below is out of
sample. Nothing here changes a pick, stake or threshold: promotion stays with the Architect, through
the repo's normal gate. A close is only known at kick-off, so the shadow cannot be bet before the
close; CLV for it is PENDING (HR35) until a pre-close SportyBet price is archived beside the close.

    python -m engine.soft_close_shadow     # fit + print + write memory/soft_close_shadow.json
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import walkforward as wf  # noqa: E402

RECORD = ROOT / "memory" / "soft_close_shadow.json"
OUTCOME, FEATURE = "over 2.5", "soft close gap"
TAG_GAP = 0.03          # a fixture whose soft close sits this far above the model is a shadow candidate
PROMOTE_SE = 0.002      # issue #251: consider promotion when gain > 0 with se under this
REJECT_GAIN = 0.001     # issue #251: reject if gain stays under this ...
REJECT_N = 1000         # ... over this many scored picks


def fit_lean(rows: list[tuple[str, float, int, float | None]]) -> dict | None:
    """Standardise the gap and fit its weight on all rows given. None while rows are too few."""
    have = [(p, y, f) for _, p, y, f in rows if isinstance(f, (int, float))]
    if len(have) < wf.MIN_TRAIN:
        return None
    mu = sum(f for *_, f in have) / len(have)
    sd = math.sqrt(sum((f - mu) ** 2 for *_, f in have) / len(have)) or 1.0
    coef = wf.fit_offset([(p, y, (f - mu) / sd) for p, y, f in have])
    return {"mu": mu, "sd": sd, "coef": coef, "rows": len(have)}


def shadow_p(model_p: float, gap: float | None, fit: dict | None) -> float | None:
    """The shadow's Over 2.5 chance; None (PENDING) when the gap or the fit is missing."""
    if fit is None or not isinstance(gap, (int, float)):
        return None
    return wf._sig(wf._logit(model_p) + fit["coef"] * (gap - fit["mu"]) / fit["sd"])


def verdict(test: dict) -> str:
    if test["scored"] == 0:
        return "PENDING"
    if test["scored"] >= REJECT_N and test["gain"] < REJECT_GAIN:
        return "REJECT (pre-registered)"
    if test["gain"] > 0 and test["se"] < PROMOTE_SE and test["gain"] > 2 * test["se"]:
        return "PROMOTION CANDIDATE (Architect decides)"
    return "KEEP WATCHING"


def build(rows: list[tuple[str, float, int, float | None]]) -> dict:
    """rows: (day, model chance, over 2.5 happened 0/1, soft close gap or None)."""
    out: dict = {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "recorded_only": True,
                 "hypothesis": "H003", "outcome": OUTCOME, "feature": FEATURE,
                 "clv": "PENDING — no pre-close SportyBet price archived beside the close yet"}
    test = wf.feature_test(rows)
    out["walk_forward"] = test
    out["verdict"] = verdict(test)
    fit = fit_lean(rows)
    out["fit"] = None if fit is None else {k: round(v, 4) if isinstance(v, float) else v for k, v in fit.items()}
    tagged = [(p, y) for _, p, y, f in rows if isinstance(f, (int, float)) and f > TAG_GAP]
    out["tagged"] = {"gap_over": TAG_GAP, "n": len(tagged),
                     "hit_rate": round(sum(y for _, y in tagged) / len(tagged), 4) if tagged else None,
                     "model_mean": round(sum(p for p, _ in tagged) / len(tagged), 4) if tagged else None}
    return out


def summary_line(rec: dict) -> str:
    t = rec["walk_forward"]
    if not t["scored"]:
        return "soft-close shadow: PENDING (too few graded fixtures with a SportyBet close)"
    return (f"soft-close shadow (H003): out of sample n{t['scored']} gain {t['gain']:+.5f} ± {t['se']:.5f}"
            f" on model Brier {t['brier_model']} · {rec['verdict']}")


def run(path: Path = RECORD) -> str:
    from backtest import features_study as fs
    rows = fs.feature_rows(fs.collect())[OUTCOME][FEATURE]
    rec = build(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return summary_line(rec)


if __name__ == "__main__":
    print(run())
