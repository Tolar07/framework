"""
NBA PROJECTION GATE (Architect 2026-10-28: "I'm giving the okay ... do what you recommend
with it"). The OK is given in advance, on the condition the Architect set: the player-built
projection (engine/nba_projection.py) touches picks only after it beats the sharp line on
games it was not fitted to. This module measures that every day and opens by itself.

  OPEN when, over the graded games whose projection was recorded at board time
  (backtest/nba_projection_study.py), ALL of:
    - at least MIN_GAMES games;
    - on the same yes/no lines, both sides, the projection's chances beat the sharp
      line's on BOTH Brier and log loss;
    - the projection's side at SportyBet's board total gains against the sharp CLOSING
      total on average (positive CLV).
  It closes again by itself if any of these stops holding.

  WHEN OPEN: a pick whose side the projection gives under 50% (it prices the other side
  as the better one) is dropped from the board — recorded under picks_dropped and graded
  like every dropped pick, never booked or sent. A pick the projection cannot price
  (moneyline, a stale sheet, no projection) is kept. The projection never ADDS a pick and
  never changes a stake.

The status is written each day to memory/nba_projection_gate.json.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from engine import nba_value as nv

ROOT = Path(__file__).parent.parent
GATE_PATH = ROOT / "memory" / "nba_projection_gate.json"
MIN_GAMES = 150


def _score(p: float, y: int) -> tuple[float, float]:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return (p - y) ** 2, -(y * math.log(p) + (1 - y) * math.log(1 - p))


def paired(recs: list[dict]) -> dict:
    """Projection vs sharp on the SAME lines: n lines, Brier and log loss of each."""
    pb = pl = sb = sl = 0.0
    n = 0
    for r in recs:
        res = r["result"]
        act = {"total": res["hs"] + res["as"], "h1_total": res["h1"], "q1_total": res["q1"],
               "spread": res["hs"] - res["as"]}
        for key, rows in (r.get("sides") or {}).items():
            for row in rows.values():
                p, s = row.get("projection"), row.get("sharp")
                if not p or not s:
                    continue
                if key == "spread":
                    y, pp, ps = int(act[key] > -p["line"]), p["home"], s["home"]
                else:
                    y, pp, ps = int(act[key] > p["line"]), p["over"], s["over"]
                b1, l1 = _score(pp, y)
                b2, l2 = _score(ps, y)
                pb, pl, sb, sl, n = pb + b1, pl + l1, sb + b2, sl + l2, n + 1
    if not n:
        return {"n": 0}
    return {"n": n, "projection": {"brier": pb / n, "logloss": pl / n}, "sharp": {"brier": sb / n, "logloss": sl / n}}


def status(recs: list[dict], clv: dict) -> dict:
    pr = paired(recs)
    why = []
    if len(recs) < MIN_GAMES:
        why.append(f"{len(recs)} graded games < {MIN_GAMES}")
    if pr["n"] and not (pr["projection"]["brier"] < pr["sharp"]["brier"]
                        and pr["projection"]["logloss"] < pr["sharp"]["logloss"]):
        why.append("does not beat the sharp line on both Brier and log loss")
    if not pr["n"]:
        why.append("no graded lines")
    if clv.get("mean_pts") is None or clv["mean_pts"] <= 0:
        why.append("no positive CLV against the sharp close")
    return {"open": not why, "why": why, "games": len(recs), "lines": pr, "clv": clv,
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}


def save(st: dict, path: Path = GATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def is_open(path: Path = GATE_PATH) -> bool:
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("open"))
    except (OSError, ValueError):
        return False


def chance(pick: dict, projection: dict | None) -> float | None:
    """The projection's chance of the pick's own side, or None when it can't price it."""
    if not projection:
        return None
    fake = SimpleNamespace(total=projection["total"], spread=projection["spread"], ml_home=None, ml_away=None)
    return nv.fair_chance(str(pick.get("market_id")), pick.get("specifier") or "", pick.get("outcome") or "", fake)


def apply(picks: list[dict], projections: list[dict], open_: bool) -> tuple[list[dict], list[dict]]:
    """(kept, dropped). Every pick records the projection's chance of its side; only an open
    gate drops the ones the projection gives under 50%."""
    by_id = {p.get("espn_id"): p.get("projection") for p in projections if p.get("espn_id")}
    kept, dropped = [], []
    for p in picks:
        c = chance(p, by_id.get(p.get("espn_id")))
        p = {**p, "projection_chance": None if c is None else round(c, 4)}
        if open_ and c is not None and c < 0.5:
            dropped.append({**p, "dropped_by": "projection gate"})
        else:
            kept.append(p)
    return kept, dropped
