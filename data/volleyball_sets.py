"""
Volleyball points by set from ESPN's public scoreboard (site.api.espn.com, free, no key), framework #591.
RECORD ONLY: feeds engine/volleyball_events.py and backtest/volleyball_events_study.py; nothing here picks or stakes.

One row per finished NCAA women's match (Aug 20 - Dec 31 of each fall season, the only free dated volleyball history):
  {"day","home","away","hs","as","sets":[[h,a], ...]}   hs/as = sets won, sets = points in each set, in order.
A match whose set scores are missing, whose count differs from hs + as, or whose set winners do not match hs / as is
skipped, PENDING - never a guessed zero (HR35). One file per day in data/cache/volleyball_sets/ (a finished day is
never re-fetched).
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

API = "https://site.api.espn.com/apis/site/v2/sports/volleyball/womens-college-volleyball/scoreboard?dates={d}&limit=1000"
CACHE = Path(__file__).parent / "cache" / "volleyball_sets"
YEARS = tuple(range(2016, 2026))
_UA = {"User-Agent": "Mozilla/5.0 (OLP XDV volleyball model)", "Accept": "application/json"}


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=_UA)  # noqa: S310 - fixed https API
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - retried, then raised
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def parse_event(e: dict) -> dict | None:
    """Set points from one scoreboard event. None (PENDING) unless completed, best-of-5 shaped, set scores add up."""
    if not ((e.get("status") or {}).get("type") or {}).get("completed"):
        return None
    comp = ((e.get("competitions") or [{}])[0]).get("competitors") or []
    try:
        h = next(t for t in comp if t.get("homeAway") == "home")
        a = next(t for t in comp if t.get("homeAway") == "away")
        hs, as_ = int(float(h["score"])), int(float(a["score"]))
        lh = [float(x["value"]) for x in h.get("linescores") or []]
        la = [float(x["value"]) for x in a.get("linescores") or []]
    except (StopIteration, KeyError, TypeError, ValueError):
        return None
    if max(hs, as_) != 3 or min(hs, as_) > 2 or len(lh) != hs + as_ or len(la) != len(lh):
        return None
    if sum(x > y for x, y in zip(lh, la)) != hs or sum(y > x for x, y in zip(lh, la)) != as_:
        return None                                    # set winners must agree with the sets-won score
    home, away = (h.get("team") or {}).get("displayName"), (a.get("team") or {}).get("displayName")
    if not home or not away:
        return None
    return {"day": (e.get("date") or "")[:10], "home": home, "away": away, "hs": hs, "as": as_,
            "sets": [[int(x), int(y)] for x, y in zip(lh, la)]}


def day_rows(d: str, get=_get) -> list[dict]:
    f = CACHE / f"{d}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    rows = [r for r in (parse_event(e) for e in get(API.format(d=d)).get("events") or []) if r]
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def days() -> list[str]:
    out = []
    for y in YEARS:
        d = date(y, 8, 20)
        while d <= date(y, 12, 31):
            out.append(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
    return out


def load(get=_get, day_list: list[str] | None = None) -> list[dict]:
    """Every parsed match, once, sorted by day. A day that will not load is skipped and counted, never invented."""
    def one(d):
        try:
            return day_rows(d, get)
        except Exception:  # noqa: BLE001
            return None
    with ThreadPoolExecutor(8) as pool:
        res = list(pool.map(one, day_list if day_list is not None else days()))
    failed = sum(r is None for r in res)
    if failed:
        print(f"{failed} days not loaded")
    seen, out = set(), []
    for rows in res:
        for r in rows or []:
            k = (r["day"], frozenset((r["home"], r["away"])))
            if k not in seen:
                seen.add(k)
                out.append(r)
    out.sort(key=lambda r: (r["day"], r["home"]))
    return out
