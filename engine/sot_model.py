"""
SHOTS-ON-TARGET RATING — an xG stand-in for leagues Understat doesn't cover
(Architect 2026-10-05: "xG beyond the top 5").

football-data.co.uk's season files carry shots on target (HST, AST) for most
main-file leagues. Each shot on target is worth the league's goals per shot on
target over the window, so a match's "shot goals" = shots on target × that
rate — a smoother measure of chance creation than goals, the same idea as xG.
Those per-match values feed the same time-weighted rating as engine/xg_model
(240-day half-life) and its Poisson scoreline grid, which the orchestrator
averages with the Dixon-Coles grid exactly as it does for Understat xG.

Used only where backtest/SOT_STUDY.md showed it improves the predictions
(SOT_LEAGUES). Leagues whose files carry no shots stay on Dixon-Coles alone.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional

from engine.xg_model import XGRatings

CACHE = Path(__file__).parent.parent / "data" / "cache"
# Leagues where the blend beat Dixon-Coles alone on BOTH 1X2 log loss and
# Over 2.5 Brier over 250+ walk-forward matches (backtest/SOT_STUDY.md).
SOT_LEAGUES: frozenset[str] = frozenset({"Championship", "Eredivisie",
                                         "Belgian Pro League", "Scottish Premiership"})


def _iso(d: str) -> Optional[str]:
    if "/" not in d:
        return d or None
    try:
        dd, mm, yy = d.split("/")
    except ValueError:
        return None
    yy = ("20" + yy) if len(yy) == 2 else yy
    return f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"


def _int(x) -> Optional[int]:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def rows_from_csv(paths) -> list[dict]:
    """[{date, home, away, hg, ag, hst, ast}] from football-data season files,
    only rows with goals AND shots on target (nothing is filled in)."""
    out = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        with open(p, encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                d = _iso((r.get("Date") or "").strip())
                hg, ag = _int(r.get("FTHG")), _int(r.get("FTAG"))
                hst, ast = _int(r.get("HST")), _int(r.get("AST"))
                home, away = (r.get("HomeTeam") or "").strip(), (r.get("AwayTeam") or "").strip()
                if None in (d, hg, ag, hst, ast) or not home or not away:
                    continue
                out.append({"date": d, "home": home, "away": away,
                            "hg": hg, "ag": ag, "hst": hst, "ast": ast})
    return sorted(out, key=lambda x: x["date"])


def ratings_from_rows(rows: list[dict], ref: str) -> Optional[XGRatings]:
    """Shot-goal ratings from rows played before `ref`; None if too few."""
    past = [r for r in rows if r["date"] < ref]
    sot = sum(r["hst"] + r["ast"] for r in past)
    goals = sum(r["hg"] + r["ag"] for r in past)
    if len(past) < 50 or sot <= 0:
        return None
    rate = goals / sot
    matches = [{"date": r["date"], "home": r["home"], "away": r["away"],
                "xh": r["hst"] * rate, "xa": r["ast"] * rate} for r in past]
    return XGRatings(matches, ref)


def ratings_for(league: str, fit_season: str, current_season: str,
                ref: Optional[str] = None) -> Optional[XGRatings]:
    """Ratings from the cached season files (last season + this season)."""
    stem = league.replace(" ", "_")
    rows = rows_from_csv([CACHE / f"{stem}_{fit_season}.csv",
                          CACHE / f"{stem}_{current_season}.csv"])
    return ratings_from_rows(rows, ref or date.today().isoformat())
