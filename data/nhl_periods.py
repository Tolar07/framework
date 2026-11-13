"""
NHL per-period goals and shots on goal from the NHL's free play-by-play (api-web.nhle.com, no key), framework #586.
RECORD ONLY: feeds engine/hockey_events.py and backtest/hockey_events_study.py; nothing here picks or stakes.

One row per finished regular-season game (regulation periods 1-3 only; overtime and shootout are excluded):
  {"id","date","home","away","g":[[h,a],[h,a],[h,a]],"s":[[h,a],[h,a],[h,a]]}
g = goals per period, s = shots on goal per period (a goal counts as a shot on goal, as the NHL counts it).
Finished seasons are cached in data/cache/nhl_periods/<season>.json (re-read, never re-fetched).
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from data import nhl_source as nhl

CACHE = Path(__file__).parent / "cache" / "nhl_periods"
SHOT_TYPES = {"shot-on-goal", "goal"}


def parse_pbp(pbp: dict) -> dict | None:
    """Per-period goals and shots on goal from one play-by-play. None (PENDING, HR35) if the game is not final or
    a regulation period has no events (never a guessed zero)."""
    if pbp.get("gameState") not in nhl.FINAL:
        return None
    hid = (pbp.get("homeTeam") or {}).get("id")
    aid = (pbp.get("awayTeam") or {}).get("id")
    if hid is None or aid is None:
        return None
    g = [[0, 0] for _ in range(3)]
    s = [[0, 0] for _ in range(3)]
    seen = [0, 0, 0]
    for p in pbp.get("plays") or []:
        pd = p.get("periodDescriptor") or {}
        n = pd.get("number")
        if pd.get("periodType") != "REG" or n not in (1, 2, 3):
            continue
        seen[n - 1] += 1
        if p.get("typeDescKey") not in SHOT_TYPES:
            continue
        owner = (p.get("details") or {}).get("eventOwnerTeamId")
        side = 0 if owner == hid else 1 if owner == aid else None
        if side is None:
            continue
        s[n - 1][side] += 1
        if p["typeDescKey"] == "goal":
            g[n - 1][side] += 1
    if min(seen) == 0:
        return None
    return {"id": pbp.get("id"), "date": (pbp.get("startTimeUTC") or "")[:10],
            "home": pbp["homeTeam"].get("abbrev"), "away": pbp["awayTeam"].get("abbrev"), "g": g, "s": s}


def season_rows(start_year: int, get=nhl._get, today: date | None = None) -> list[dict]:
    """Every finished regular-season game of the season starting in start_year, with per-period goals and shots."""
    today = today or date.today()
    cache = CACHE / f"{start_year}{start_year + 1}.json"
    done = date(start_year + 1, 6, 30) < today
    if done and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    def one(r: dict) -> dict | None:
        try:
            return parse_pbp(get(f"{nhl.API}/gamecenter/{r['id']}/play-by-play"))
        except Exception:  # noqa: BLE001 — one failed game is PENDING, not a guess
            return None

    games = [r for r in nhl.season(start_year, get, today) if r["type"] == 2]
    with ThreadPoolExecutor(8) as ex:
        out = [x for x in ex.map(one, games) if x]
    out.sort(key=lambda r: (r["date"], r["id"]))
    if done:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out), encoding="utf-8")
    return out
