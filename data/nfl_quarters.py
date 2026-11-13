"""
NFL points by quarter from ESPN's public scoreboard (site.api.espn.com, free, no key), framework #588.
RECORD ONLY: feeds engine/nfl_events.py and backtest/nfl_events_study.py; nothing here picks or stakes.

One row per finished regular-season game with four quarter scores that add up to the final score:
  {"id","date","home","away","r":[[h,a] x 4], "ot": bool}
r = points by quarter 1-4 (overtime points are not in r; ot marks a game that went to overtime). A game whose quarter
scores are missing or do not add up is skipped, PENDING - never a guessed zero (HR35). Finished seasons are cached in
data/cache/nfl_quarters/<season>.json (re-read, never re-fetched). The scoreboard answers per week, not per date range.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date
from pathlib import Path

API = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={y}&seasontype=2&week={w}&limit=100"
CACHE = Path(__file__).parent / "cache" / "nfl_quarters"
_UA = {"User-Agent": "Mozilla/5.0 (OLP XDV NFL model)", "Accept": "application/json"}


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=_UA)  # noqa: S310 - fixed https API
            with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - retried, then raised
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def parse_game(e: dict) -> dict | None:
    """Quarter points from one scoreboard event. None (PENDING) unless completed, with four or more quarter scores per
    side whose total equals the final score."""
    if not ((e.get("status") or {}).get("type") or {}).get("completed"):
        return None
    comp = ((e.get("competitions") or [{}])[0]).get("competitors") or []
    try:
        h = next(t for t in comp if t.get("homeAway") == "home")
        a = next(t for t in comp if t.get("homeAway") == "away")
        fh, fa = int(float(h["score"])), int(float(a["score"]))
    except (StopIteration, KeyError, TypeError, ValueError):
        return None
    lh = [x.get("value") for x in h.get("linescores") or []]
    la = [x.get("value") for x in a.get("linescores") or []]
    if len(lh) < 4 or len(lh) != len(la) or None in lh or None in la:
        return None
    if (sum(lh), sum(la)) != (fh, fa):
        return None                                    # period scores that do not add up are not kept
    home, away = (h.get("team") or {}).get("displayName"), (a.get("team") or {}).get("displayName")
    if not home or not away:
        return None
    return {"id": e.get("id"), "date": (e.get("date") or "")[:10], "home": home, "away": away,
            "r": [[int(lh[i]), int(la[i])] for i in range(4)], "ot": len(lh) > 4}


def season_rows(year: int, get=_get, today: date | None = None) -> list[dict]:
    """Every finished regular-season game of the season (weeks 1-18) with points by quarter."""
    today = today or date.today()
    cache = CACHE / f"{year}.json"
    done = date(year + 1, 3, 1) < today
    if done and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    out: dict = {}
    for w in range(1, 19):
        for e in get(API.format(y=year, w=w)).get("events") or []:
            row = parse_game(e)
            if row:
                out[row["id"]] = row
    rows = sorted(out.values(), key=lambda r: (r["date"], r["id"]))
    if done:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rows), encoding="utf-8")
    return rows
