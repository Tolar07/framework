"""
NBA LADDERS — what spread SportyBet's points ladders assume (order 41 paper
board; Architect 2026-10-07: "build A and B together and C").

SportyBet prices 11-18 lines per game on one points market, all from one
centre line and some assumed spread around it. If that spread is narrower
than how real NBA scores land (the full-game total lands ±18.0 points around
the sharp line, backtest/NBA_STUDY.md Q5), its far lines are priced too
generously — or too meanly if wider. That would be a lasting edge, not a
one-off, so every ladder is saved and measured.

For each line the margin-free Over chance p is taken from its two prices.
If scores land ~ Normal(centre, spread), then
        line = centre + spread x z,     z = Φ⁻¹(1 − p)
so an ordinary least-squares line through (z, line) gives the ladder's own
centre and spread. Handicap ladders are read the same way, as the home
margin: a home line -h is covered when margin > h.

Snapshots go to output/nba_ladders/<UTC date>.jsonl, one row per game per
look; backtest/nba_ladder_study.py reads them.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from statistics import NormalDist

from engine import nba_value as nv

LADDER_DIR = Path(__file__).parent.parent / "output" / "nba_ladders"
# SportyBet points markets read as ladders: totals, team totals, regulation
# total, and the full-game / 1st-half / quarter handicaps (as home margin).
TOTAL_MARKETS = ("225", "227", "228", "18")
HCP_MARKETS = ("223", "66", "303")
_N = NormalDist()


def _num(spec: str, key: str) -> float | None:
    m = re.search(rf"{key}=(-?\d+(?:\.\d+)?)", spec or "")
    return float(m.group(1)) if m else None


def ladders(event: dict) -> dict[str, list[list[float]]]:
    """{market key: [[line, over price, under price], ...]} for one SportyBet event.
    A quarter handicap is keyed '303/q<n>'. Handicap rows are [h, home price,
    away price] with h the HOME handicap; whole-number lines are kept (they are
    priced) but left out of the fit."""
    out: dict[str, list[list[float]]] = {}
    for m in event.get("markets", []):
        mid, spec = str(m.get("id")), m.get("specifier") or ""
        if mid not in TOTAL_MARKETS + HCP_MARKETS:
            continue
        px = {}
        for o in m.get("outcomes", []):
            try:
                px[(o.get("desc") or "").split()[0]] = float(o.get("odds"))
            except (TypeError, ValueError):
                continue
        if mid in TOTAL_MARKETS:
            line, a, b = _num(spec, "total"), px.get("Over"), px.get("Under")
            key = mid
        else:
            line, a, b = _num(spec, "hcp"), px.get("Home"), px.get("Away")
            q = _num(spec, "quarternr")
            key = f"303/q{int(q)}" if mid == "303" and q else mid
        if line is None or not a or not b or a <= 1 or b <= 1:
            continue
        out.setdefault(key, []).append([line, a, b])
    for rows in out.values():
        rows.sort()
    return out


def fit(key: str, rows: list[list[float]]) -> tuple[float, float, int] | None:
    """(centre, spread, lines used) of one ladder, or None with < 3 usable lines.
    For a handicap the centre is the expected HOME margin."""
    pts = []
    hcp = key.startswith(HCP_MARKETS)
    for line, a, b in rows:
        p = nv.devig(a, b)               # Over chance (totals) / home-covers chance
        if not 0.02 < p < 0.98 or (hcp and line == int(line)):
            continue                     # a whole handicap line can push: not a clean chance
        # totals: Over lands when total > line; handicap: home covers when margin > -h
        pts.append((_N.inv_cdf(1 - p), -line if hcp else line))
    if len(pts) < 3:
        return None
    n = len(pts)
    mz = sum(z for z, _ in pts) / n
    my = sum(y for _, y in pts) / n
    szz = sum((z - mz) ** 2 for z, _ in pts)
    if szz < 1e-9:
        return None
    sd = sum((z - mz) * (y - my) for z, y in pts) / szz
    if sd <= 0:
        return None
    return round(my - sd * mz, 2), round(sd, 2), n


def snapshot_row(now: datetime, stage: str, event: dict, home: str, away: str, g) -> dict:
    """One saved look at one game: the sharp line, every ladder and its fit."""
    lads = ladders(event)
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "stage": stage,
            "event_id": event.get("eventId"), "espn_id": getattr(g, "id", None),
            "tip": getattr(g, "tip", None), "home": home, "away": away,
            "sharp": {"ml_home": g.ml_home, "ml_away": g.ml_away,
                      "spread": g.spread, "total": g.total},
            "ladders": lads,
            "fits": {k: fit(k, rows) for k, rows in lads.items()}}


def save(rows: list[dict], now: datetime, folder: Path = LADDER_DIR) -> Path | None:
    if not rows:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{now:%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return path


def load(folder: Path = LADDER_DIR) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows
