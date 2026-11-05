"""
NHL results from the NHL's own free API (api-web.nhle.com, no key) for the ice hockey model
and its backtest (standing order 50, multi-sport rollout; Architect 2026-11-05).

One row per finished regular-season or playoff game:
  {"id", "season", "type", "date", "ko", "home", "away", "hs", "as", "period"}
period = REG / OT / SO. hs/as are FINAL scores (overtime and shootout included: the shootout
winner gets +1, as the NHL scores it). Regulation scores: reg_score() — a game that went to OT
or a shootout was level after 60 minutes at the loser's score.

Finished seasons are cached in data/cache/nhl/<season>.json (re-read, never re-fetched).
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api-web.nhle.com/v1"
CACHE = Path(__file__).parent / "cache" / "nhl"
_UA = "Mozilla/5.0 (OLP XDV hockey model)"
FINAL = {"OFF", "FINAL"}


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — retried, then raised
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def team_name(t: dict) -> str:
    place = (t.get("placeName") or {}).get("default", "")
    common = (t.get("commonName") or {}).get("default", "")
    return f"{place} {common}".strip()


def _row(g: dict) -> dict | None:
    if g.get("gameState") not in FINAL or g.get("gameType") not in (2, 3):
        return None
    h, a = g.get("homeTeam") or {}, g.get("awayTeam") or {}
    if h.get("score") is None or a.get("score") is None:
        return None
    return {"id": g["id"], "season": g.get("season"), "type": g["gameType"],
            "date": (g.get("startTimeUTC") or "")[:10], "ko": g.get("startTimeUTC"),
            "home": h.get("abbrev"), "away": a.get("abbrev"),
            "home_name": team_name(h), "away_name": team_name(a),
            "hs": int(h["score"]), "as": int(a["score"]),
            "period": (g.get("gameOutcome") or {}).get("lastPeriodType", "REG")}


def games_between(start: date, end: date, get=_get) -> list[dict]:
    """Every finished game from start to end (inclusive), one API call per week."""
    out, seen, d = [], set(), start
    while d <= end:
        wk = get(f"{API}/schedule/{d.isoformat()}")
        for day in wk.get("gameWeek") or []:
            if not (start.isoformat() <= day.get("date", "") <= end.isoformat()):
                continue
            for g in day.get("games") or []:
                r = _row(g)
                if r and r["id"] not in seen:
                    seen.add(r["id"])
                    out.append(r)
        d += timedelta(days=7)
    return sorted(out, key=lambda r: (r["ko"] or "", r["id"]))


def season(start_year: int, get=_get, today: date | None = None) -> list[dict]:
    """The season starting in October of start_year (e.g. 2024 -> 2024-25)."""
    today = today or date.today()
    end = date(start_year + 1, 6, 30)
    cache = CACHE / f"{start_year}{start_year + 1}.json"
    if end < today and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    rows = games_between(date(start_year, 9, 25), min(end, today), get)
    if end < today:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def reg_score(r: dict) -> tuple[int, int]:
    """The score after 60 minutes."""
    if r.get("period") in ("OT", "SO"):
        low = min(r["hs"], r["as"])
        return low, low
    return r["hs"], r["as"]


def history(seasons: int = 3, today: date | None = None, get=_get) -> list[dict]:
    """The last `seasons` finished seasons plus the current one, oldest first."""
    today = today or date.today()
    cur = today.year if today.month >= 9 else today.year - 1
    out: list[dict] = []
    for y in range(cur - seasons, cur + 1):
        out += season(y, get, today)
    return out
