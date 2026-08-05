"""TheSportsDB Club Friendlies sandbox source (verified id 4569, 2026-08-05).

WHY A SANDBOX
  Pre-season (Aug) has no league fixtures, so the main pipeline idles during
  the wait for the season. Club friendlies exercise the SAME machinery
  end-to-end — fixture sourcing, model rating, paper-leg logging, settlement,
  brain recording — on real live matches.

HONESTY (HR35)
  - No friendly ODDS exist in any framework source (The Odds API has no
    friendly sport — verified 2026-08-05), so sandbox CLV is always
    NO DATA — PENDING. This sandbox tests the MACHINERY, not edge.
  - TheSportsDB's 'Club Friendlies' competition feed (eventsseason 4569) caps
    at 15 winter friendlies; the current August pre-season matches are only
    reachable per-TEAM via eventsnext. Team IDs are resolved by NAME and
    cached; an unresolvable club is skipped (its friendlies read
    NO DATA — PENDING, never guessed).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib import request

from data.thesportsdb_fixtures import _get_key

CLUB_FRIENDLIES_ID = "4569"  # verified by name against a live event 2026-08-05
API_BASE = "https://www.thesportsdb.com/api/v1/json"
TEAM_ID_CACHE = (Path(__file__).parent.parent / "data" / "cache"
                 / "thesportsdb_team_ids.json")
EVENTS_CACHE = (Path(__file__).parent.parent / "data" / "cache"
                / "thesportsdb_friendlies")
FRIENDLIES_MAX_AGE_SECONDS = 6 * 3600

KEY = "123"  # public test key — the framework's verified leagues use the same


@dataclass
class SandboxFixture:
    id_event: str
    home_team: str  # TheSportsDB names (raw, before mapping)
    away_team: str
    date: str       # ISO yyyy-mm-dd
    kickoff_utc: str


def _json(url: str):
    req = request.Request(url)
    with request.urlopen(req, timeout=20) as r:
        return json.load(r)


# ---- team ID resolution (one-time, cached) --------------------------------
def _load_team_ids() -> dict[str, int]:
    if TEAM_ID_CACHE.exists():
        try:
            return {k: int(v) for k, v in
                    json.loads(TEAM_ID_CACHE.read_text(encoding="utf-8")).items()}
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return {}


def _save_team_ids(m: dict[str, int]) -> None:
    TEAM_ID_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TEAM_ID_CACHE.write_text(json.dumps(m, indent=1), encoding="utf-8")


def _search_team(name: str) -> Optional[int]:
    """TheSportsDB team id by NAME. Returns None if unresolved — never guesses."""
    url = f"{API_BASE}/{KEY}/searchteams.php?t={name}"
    try:
        data = _json(url)
    except Exception:
        return None
    teams = data.get("teams") or []
    if not teams:
        return None
    # Prefer an exact, case-insensitive name match; else the first result.
    for t in teams:
        if (t.get("strTeam") or "").lower() == name.lower():
            return int(t["idTeam"])
    return int(teams[0]["idTeam"])


def resolve_team_ids(team_keys: list[str]) -> dict[str, int]:
    """{model_key: thesportsdb_id} for the subset resolvable by name. Cached on
    disk so resolution is a one-time cost, not a per-run one."""
    known = _load_team_ids()
    missing = [k for k in team_keys if k not in known]
    for k in missing:
        tid = _search_team(k)
        if tid is not None:
            known[k] = tid
    _save_team_ids(known)
    return known


# ---- upcoming friendly fixtures (per-team, deduped, cached) ----------------
def _events_cache_path(team_id: int) -> Path:
    return EVENTS_CACHE / f"{team_id}.json"


def _team_next_events(team_id: int, _retry: bool = True) -> list[dict]:
    p = _events_cache_path(team_id)
    if p.exists():
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - blob.get("fetched_at", 0) <= FRIENDLIES_MAX_AGE_SECONDS:
                return blob.get("events", [])
        except (json.JSONDecodeError, OSError):
            pass
    url = f"{API_BASE}/{KEY}/eventsnext.php?id={team_id}"
    try:
        evs = (_json(url)).get("events") or []
    except Exception:
        if _retry:
            time.sleep(0.4)
            return _team_next_events(team_id, _retry=False)
        return []  # a FAILED call is never cached as "empty" — retry next run
    EVENTS_CACHE.mkdir(parents=True, exist_ok=True)
    _events_cache_path(team_id).write_text(
        json.dumps({"fetched_at": time.time(), "events": evs}), encoding="utf-8")
    time.sleep(0.05)  # be polite to the shared test key
    return evs


def upcoming_friendlies(team_ids: dict[str, int],
                        days_ahead: int = 14) -> list[SandboxFixture]:
    """Collect upcoming 'Club Friendlies' events for the given teams. Deduped by
    idEvent (two clubs' eventsnext both return the same fixture)."""
    horizon = date.today() + timedelta(days=days_ahead)
    seen: set[str] = set()
    out: list[SandboxFixture] = []
    for tid in team_ids.values():
        for e in _team_next_events(tid):
            league = (e.get("strLeague") or "").lower()
            if "friend" not in league:
                continue  # league fixtures belong to the main pipeline, not here
            eid = e.get("idEvent")
            if not eid or eid in seen:
                continue
            day = (e.get("dateEvent") or "")[:10]
            if not day:
                continue
            try:
                if date.fromisoformat(day) > horizon:
                    continue
            except ValueError:
                continue
            home, away = e.get("strHomeTeam"), e.get("strAwayTeam")
            if not home or not away:
                continue
            seen.add(eid)
            out.append(SandboxFixture(id_event=str(eid), home_team=home,
                                      away_team=away, date=day,
                                      kickoff_utc=e.get("dateEvent", "")))
    out.sort(key=lambda f: f.date)
    return out


# ---- settlement: a friendly event's final result ---------------------------
def lookup_event(id_event: str) -> Optional[dict]:
    """The event's CURRENT score/status via lookupevent. Returns
    {"home","away","fthg","ftag","status"} once finished, else None."""
    url = f"{API_BASE}/{KEY}/lookupevent.php?id={id_event}"
    try:
        evs = (_json(url)).get("events") or []
    except Exception:
        return None
    if not evs:
        return None
    e = evs[0]
    status = (e.get("strStatus") or "").upper()
    fthg = e.get("intHomeScore")
    ftag = e.get("intAwayScore")
    if status != "FT" or fthg is None or ftag is None:
        return None  # not finished — remains PENDING, never guessed
    return {"home": e.get("strHomeTeam"), "away": e.get("strAwayTeam"),
            "fthg": int(fthg), "ftag": int(ftag), "status": status}
