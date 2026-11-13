"""
MLB runs by innings from the MLB StatsAPI schedule + linescore (statsapi.mlb.com, free, no key), framework #587.
RECORD ONLY: feeds engine/baseball_events.py and backtest/baseball_events_study.py; nothing here picks or stakes.

One row per finished regular-season game that went at least nine innings (shortened games, seven-inning
doubleheader games and games with a missing inning are skipped, PENDING - never a guessed zero, HR35):
  {"id","date","home","away","r":[[h,a] x 9]}
r = runs by inning 1-9 (extra innings are not in r). A bottom of the 9th that was not played (home side already
ahead) is a true 0. Finished seasons are cached in data/cache/mlb_innings/<season>.json (re-read, never re-fetched).
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://statsapi.mlb.com/api/v1/schedule"
CACHE = Path(__file__).parent / "cache" / "mlb_innings"
_UA = "Mozilla/5.0 (OLP XDV baseball model)"


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310 - fixed https API
            with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - retried, then raised
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def parse_game(g: dict) -> dict | None:
    """Runs by inning 1-9 from one schedule game (hydrate=linescore). None (PENDING) unless final, regular season,
    nine or more innings and every inning 1-8 (and the away 9th) has a run count."""
    if (g.get("status") or {}).get("abstractGameState") != "Final" or g.get("gameType") != "R":
        return None
    inn = (g.get("linescore") or {}).get("innings") or []
    if len(inn) < 9:
        return None
    teams = g.get("teams") or {}
    home = ((teams.get("home") or {}).get("team") or {}).get("name")
    away = ((teams.get("away") or {}).get("team") or {}).get("name")
    if not home or not away:
        return None
    r: list[list[int]] = []
    for i in range(9):
        h, a = (inn[i].get("home") or {}).get("runs"), (inn[i].get("away") or {}).get("runs")
        if a is None or (h is None and i != 8):
            return None                       # a missing count is PENDING, not a zero
        r.append([h or 0, a])
    return {"id": g.get("gamePk"), "date": g.get("officialDate") or (g.get("gameDate") or "")[:10],
            "home": home, "away": away, "r": r}


def season_rows(year: int, get=_get, today: date | None = None) -> list[dict]:
    """Every finished regular-season game of the season with runs by inning (monthly requests)."""
    today = today or date.today()
    cache = CACHE / f"{year}.json"
    done = date(year, 11, 30) < today
    if done and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    out: dict = {}
    start = date(year, 3, 15)
    while start <= min(date(year, 10, 5), today):
        end = min(start + timedelta(days=13), date(year, 10, 5), today)
        url = f"{API}?sportId=1&gameType=R&startDate={start}&endDate={end}&hydrate=linescore"
        for d in get(url).get("dates") or []:
            for g in d.get("games") or []:
                row = parse_game(g)
                if row:
                    out[row["id"]] = row
        start = end + timedelta(days=1)
    rows = sorted(out.values(), key=lambda r: (r["date"], r["id"]))
    if done:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rows), encoding="utf-8")
    return rows
