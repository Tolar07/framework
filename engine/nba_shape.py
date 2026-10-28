"""
NBA GAME SHAPE — the basketball version of football's likely scores
(engine/scoreline.py, Architect 2026-10-28: "every football feature is built for NBA too").

The NBA pricing already reads the final total and the home winning margin as
Normal curves around the sharp line (engine/nba_value.py TOTAL_SD / MARGIN_SD,
season refits included). This reads the same curves as a direction for the game:
a typical final score, the winning-margin bands (1-5 / 6-10 / 11+ each way) and the
likeliest 10-point total bands.

A LABEL ONLY. Nothing selects, stakes or books on it. Every priced game keeps its
bands in the NBA picks file and the scorecard grades them, so whether the bands
can be trusted is measured before anything is wired to them.
"""
from __future__ import annotations

import math

from engine import nba_value as nv

MARGIN_BANDS = ((1, 5), (6, 10), (11, 99))
TOTAL_STEP = 10


def _cdf(x: float, mean: float, sd: float) -> float:
    return 0.5 * (1 + math.erf((x - mean) / (sd * math.sqrt(2))))


def shape(total: float | None, spread: float | None) -> dict | None:
    """Bands from the sharp total and home spread, or None without both (HR35)."""
    if total is None or spread is None:
        return None
    m, msd, tsd = -spread, nv.MARGIN_SD, nv.TOTAL_SD   # read now: season refits apply
    tie = _cdf(0.5, m, msd) - _cdf(-0.5, m, msd)        # no ties in the NBA (overtime)
    margin = {}
    for lo, hi in MARGIN_BANDS:
        name = f"{lo}-{hi}" if hi < 99 else f"{lo}+"
        margin[f"home {name}"] = (_cdf(hi + 0.5, m, msd) - _cdf(lo - 0.5, m, msd)) / (1 - tie)
        margin[f"away {name}"] = (_cdf(-lo + 0.5, m, msd) - _cdf(-hi - 0.5, m, msd)) / (1 - tie)
    start = int((total - 3 * tsd) // TOTAL_STEP * TOTAL_STEP)
    bands = {}
    for lo in range(start, int(total + 3 * tsd) + TOTAL_STEP, TOTAL_STEP):
        bands[f"{lo}-{lo + TOTAL_STEP - 1}"] = _cdf(lo + TOTAL_STEP - 0.5, total, tsd) - _cdf(lo - 0.5, total, tsd)
    return {"score": [round((total + m) / 2), round((total - m) / 2)],
            "margin": {k: round(v, 4) for k, v in margin.items()},
            "total": {k: round(v, 4) for k, v in bands.items()}}


def _top(d: dict, n: int) -> list[tuple[str, float]]:
    return sorted(d.items(), key=lambda kv: -kv[1])[:n]


def board_line(sh: dict | None, home: str, away: str) -> str | None:
    if not sh:
        return None
    side = {"home": home, "away": away}
    mg = " · ".join(f"{side[k.split()[0]]} by {k.split()[1]} {round(p * 100)}%"
                    for k, p in _top(sh["margin"], 3))
    tt = " · ".join(f"{k} {round(p * 100)}%" for k, p in _top(sh["total"], 3))
    return (f"Game shape (sharp line, label only): typical {sh['score'][0]}-{sh['score'][1]} | "
            f"{mg} | total {tt}")


def grade(sh: dict, score: str) -> dict | None:
    """The bands the final score fell in, and the chance the shape gave each."""
    try:
        hs, as_ = (int(x) for x in score.split("-"))
    except (AttributeError, ValueError):
        return None
    d = hs - as_
    if d == 0:
        return None
    lo_hi = next((lo, hi) for lo, hi in MARGIN_BANDS if lo <= abs(d) <= hi)
    mkey = f"{'home' if d > 0 else 'away'} " + (f"{lo_hi[0]}-{lo_hi[1]}" if lo_hi[1] < 99 else f"{lo_hi[0]}+")
    t = hs + as_
    tkey = next((k for k in sh["total"] if int(k.split("-")[0]) <= t <= int(k.split("-")[1])), None)
    return {"margin_p": sh["margin"][mkey], "margin_top": mkey == _top(sh["margin"], 1)[0][0],
            "total_p": sh["total"].get(tkey, 0.0) if tkey else 0.0,
            "total_top": tkey == _top(sh["total"], 1)[0][0]}


def check(rows: list[tuple[dict, str]]) -> list[str]:
    """Scorecard line: how often the likeliest band landed v what the shape said."""
    graded = [(sh, x) for sh, sc in rows if sh and (x := grade(sh, sc)) is not None]
    if len(graded) < 10:
        return []
    n = len(graded)
    said_m = sum(_top(sh["margin"], 1)[0][1] for sh, _ in graded) / n
    said_t = sum(_top(sh["total"], 1)[0][1] for sh, _ in graded) / n
    hit_m = sum(x["margin_top"] for _, x in graded) / n
    hit_t = sum(x["total_top"] for _, x in graded) / n
    return [f"Game shape check ({n} games): likeliest margin band landed {100 * hit_m:.0f}% "
            f"(said {100 * said_m:.0f}%) · likeliest total band {100 * hit_t:.0f}% (said {100 * said_t:.0f}%)"]
