"""
NCAA LINES — a fair chance for every SportyBet NCAA men's basketball side from the sharp line, the
way engine/nba_value.py prices the NBA (Architect 2026-11-05: widen basketball beyond the NBA).

The sharp line is ESPN's odds feed (DraftKings / ESPN BET, the pre-tip line). The shapes come from
backtest/NCAA_STUDY.md (1,567 games of 2025-26 with a line; Normal fits: 70% inside ±1 SD):

    winner (219)          the moneyline with its margin removed
    handicap (223)        home margin ~ Normal(-spread + MARGIN_BIAS, MARGIN_SD)
    total (225)           final total ~ Normal(total + TOTAL_BIAS, TOTAL_SD)
    1st-half total (68)   ~ Normal(H1_SHARE x total, H1_SD)

Whole-number lines can push and are never priced. Used by engine/world_basketball.py (PAPER).
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timedelta
from math import erf, sqrt

from engine import exchange as ex

TOTAL_BIAS, TOTAL_SD = 0.56, 17.22
MARGIN_BIAS, MARGIN_SD = -0.41, 11.38
H1_SHARE, H1_SD = 0.4735, 10.41
_SB = ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
       "?dates={d}&groups=50&limit=400")
_ODDS = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{e}"
         "/competitions/{e}/odds")
_CACHE: dict[str, dict | None] = {}


def _get(url: str) -> dict | None:
    if url in _CACHE:
        return _CACHE[url]
    out = None
    for i in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "olp-ncaa"}),  # noqa: S310
                                        timeout=30) as r:
                out = json.loads(r.read())
                break
        except Exception:  # noqa: BLE001 — missing data is no price, never a guess
            time.sleep(1 + i)
    _CACHE[url] = out
    return out


def _phi(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def _american(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return 1 + (v / 100 if v > 0 else 100 / -v) if v else None


def games(day: datetime) -> list[dict]:
    """ESPN's Division I games on one US date: id, tip, every name form of both teams."""
    blob = _get(_SB.format(d=day.strftime("%Y%m%d"))) or {}
    out = []
    for e in blob.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        t = {c.get("homeAway"): c.get("team") or {} for c in comp.get("competitors") or []}
        if "home" not in t or "away" not in t:
            continue

        def names(x: dict) -> list[str]:
            return [n for n in (x.get("displayName"), x.get("shortDisplayName"), x.get("location"), x.get("name"))
                    if n]
        out.append({"id": e["id"], "tip": ex._dt(e.get("date")), "home": names(t["home"]), "away": names(t["away"])})
    return out


def match(home: str, away: str, ko: datetime, gs: list[dict]) -> dict | None:
    best, score = None, 0.0
    for g in gs:
        if g["tip"] is None or abs(g["tip"] - ko) > timedelta(minutes=30):
            continue
        sh = max(ex.alike(home, n) for n in g["home"])
        sa = max(ex.alike(away, n) for n in g["away"])
        if min(sh, sa) >= 0.8 and sh + sa > score:
            best, score = g, sh + sa
    return best


def line(g: dict) -> dict | None:
    """{total, spread (home), ml_home, ml_away, provider} from ESPN's odds feed, or None."""
    blob = _get(_ODDS.format(e=g["id"])) or {}
    items = [i for i in blob.get("items") or [] if "Live" not in ((i.get("provider") or {}).get("name") or "")]
    if not items:
        return None
    o = items[0]
    try:
        total = float(o["overUnder"]) if o.get("overUnder") is not None else None
        spread = float(o["spread"]) if o.get("spread") is not None else None
    except (TypeError, ValueError):
        return None
    return {"total": total, "spread": spread, "provider": (o.get("provider") or {}).get("name"),
            "ml_home": _american((o.get("homeTeamOdds") or {}).get("moneyLine")),
            "ml_away": _american((o.get("awayTeamOdds") or {}).get("moneyLine"))}


def fair(key: str, ln: dict) -> float | None:
    """The fair chance of one SportyBet NCAA side ("B:<market>|<spec>|<outcome>") from the sharp line."""
    mid, spec, out = (key[2:].split("|") + ["", ""])[:3]
    o = out.strip().lower()
    if mid == "219" and o in ("home", "away") and ln.get("ml_home") and ln.get("ml_away"):
        ih, ia = 1 / ln["ml_home"], 1 / ln["ml_away"]
        return (ih if o == "home" else ia) / (ih + ia)
    if mid == "223" and ln.get("spread") is not None:
        m = re.fullmatch(r"(home|away) \(([+-]?[\d.]+)\)", o)
        if not m or abs(float(m.group(2))) % 1 != 0.5:
            return None
        mean = -ln["spread"] + MARGIN_BIAS                     # expected home margin
        own = float(m.group(2))                                # the side's own handicap
        p_home_covers = 1 - _phi((-own - mean) / MARGIN_SD) if m.group(1) == "home" else None
        if p_home_covers is not None:
            return p_home_covers
        return _phi((own - mean) / MARGIN_SD)                  # away covers: home margin < own line
    if mid in ("225", "68") and ln.get("total") is not None:
        m = re.search(r"total=([\d.]+)", spec)
        if not m or float(m.group(1)) % 1 != 0.5 or not o.startswith(("over", "under")):
            return None
        t = float(m.group(1))
        mean, sd = ((ln["total"] + TOTAL_BIAS, TOTAL_SD) if mid == "225" else (H1_SHARE * ln["total"], H1_SD))
        p_over = 1 - _phi((t - mean) / sd)
        return p_over if o.startswith("over") else 1 - p_over
    return None
