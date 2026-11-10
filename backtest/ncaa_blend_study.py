"""
NCAA BLEND STUDY (framework#395; twin of backtest/nba_blend_study.py). RECORD ONLY.

For every graded NCAA game with an ESPN moneyline (data/ncaa_graded/games.jsonl, written nightly by
engine/ncaa_recal.py) two chances that the home side wins:
    model   Normal(-spread + MARGIN_BIAS, MARGIN_SD): the handicap shape engine/ncaa_lines.py prices lines with
    market  the ESPN moneyline with its margin removed
Does w x model + (1 - w) x market predict better than the market alone? Walk-forward: the newest ~20% of days is the
HOLDOUT; w is the best of 0..1 in 0.05 steps on the earlier games by log loss; the holdout log loss of w=0 (market),
w=1 (model) and the fitted blend are written to backtest/NCAA_BLEND_STUDY.md. Below MIN_FIT / MIN_HOLDOUT games it
says PENDING (HR35). Nothing reads the result: no pick rule, stake or threshold changes.

    python backtest/ncaa_blend_study.py
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT)]

from engine import ncaa_lines as nl  # noqa: E402
from engine import ncaa_recal as rc  # noqa: E402

OUT = ROOT / "backtest" / "NCAA_BLEND_STUDY.md"
GRID = [i / 20 for i in range(21)]
MIN_FIT, MIN_HOLDOUT = 300, 75


def sides(rows: list[dict]) -> list[dict]:
    """Home-win outcomes with both chances (the moneyline includes overtime, so OT games count)."""
    out = []
    for r in rows:
        if not r.get("ml_home") or not r.get("ml_away") or r["hs"] == r["as"]:
            continue
        ih, ia = 1 / r["ml_home"], 1 / r["ml_away"]
        model = nl._phi((-r["spread"] + nl.MARGIN_BIAS) / nl.MARGIN_SD)
        out.append({"day": r["day"], "model": model, "market": ih / (ih + ia), "won": int(r["hs"] > r["as"])})
    return out


def _ll(rows: list[dict], w: float) -> float:
    s = 0.0
    for r in rows:
        p = min(max(w * r["model"] + (1 - w) * r["market"], 1e-4), 1 - 1e-4)
        s -= math.log(p if r["won"] else 1 - p)
    return s / len(rows)


def study(rows: list[dict]) -> dict:
    data = sides(rows)
    fit, hold = rc.split(data)
    if len(fit) < MIN_FIT or len(hold) < MIN_HOLDOUT:
        return {"status": "PENDING", "games": len(data), "fit": len(fit), "holdout": len(hold)}
    w = min(GRID, key=lambda x: _ll(fit, x))
    ll = {"market": _ll(hold, 0.0), "model": _ll(hold, 1.0), "blend": _ll(hold, w)}
    return {"status": "OK", "fit": len(fit), "holdout": len(hold), "w": w,
            "holdout_log_loss": {k: round(v, 5) for k, v in ll.items()}, "blend_beats_market": ll["blend"] < ll["market"]}


def render(res: dict) -> str:
    head = ["# NCAA BLEND STUDY — handicap-shape model vs the ESPN moneyline (home win)", "",
            f"Written by `backtest/ncaa_blend_study.py` on {datetime.now(UTC):%Y-%m-%d}. Record only.", ""]
    if res["status"] == "PENDING":
        return "\n".join(head + [f"PENDING: {res['games']} graded games with a moneyline (fit {res['fit']}, "
                                 f"holdout {res['holdout']}); needs fit >= {MIN_FIT} and holdout >= {MIN_HOLDOUT}."]) + "\n"
    ll = res["holdout_log_loss"]
    return "\n".join(head + [
        f"Fit {res['fit']} games, holdout {res['holdout']} (newest days). Best weight on the model w = {res['w']:.2f}.", "",
        "| Holdout log loss (lower is better) | market only | model only | blend |", "|---|---:|---:|---:|",
        f"| | {ll['market']:.5f} | {ll['model']:.5f} | {ll['blend']:.5f} |", "",
        "Blend beats the market on the holdout." if res["blend_beats_market"] else "The market alone holds."]) + "\n"


def main() -> int:
    text = render(study(rc.load()))
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
