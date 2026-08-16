"""
Team-state intelligence via API-Football — manager, squad hash, derived
formation for every whitelisted league (ID417).

WHY
  The engine has promoted-club handling but NO slots for low-block / absentees /
  tier-drop / manager-bounce. Feeding team-state into the brain means those
  adjustments can be built as engine *actions* on top of real data, rather than
  guessed. This module is the FETCH layer: it pulls manager, squad composition,
  and recent formation data from api-football and hands them to brain/store.py
  for persistence. The derivation of formation from recent match lineups is
  stamped ◇ DERIVED (ID403) — it is computed, not fetched.

PLAN-AWARE
  Free plan:  coaches/squads/lineups for seasons ≤ 2024.
  Paid plan:  current-season team-state unlocks.

  is_paid_plan() fails CLOSED (a probe failure keeps the free gate).

WHAT THIS DELIBERATELY DOES NOT DO
  - No tactical profile guessing (HR35): if no lineups are available, formation
    stays None — it is a DERIVED field that requires source data to derive from.
  - No Transfermarkt scraping (ToS exposure flagged for Architect decision).
  - No fabrication of manager changes: the API returns what it returns.

ID404 TIER: T1 (api-football.com, structured/official).

ID417: team_state table in brain/store.py stores these rows.
DERIVED FIELDS: formation (◇), squad_hash (◇ — a hash IS a derivation).
DIRECT FIELDS: manager_id, manager_name, manager_since (fetched verbatim).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from data.multi_source import SourceNoData
from data.retry import get_protected
from data import api_football_plan
from engine.league_registry import registry, get_api_football_id

API_BASE = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).parent / "cache" / "api_football"
FREE_TIER_LAST_SEASON = 2024
# How many recent fixtures to scan for formation derivation. 5 matches is a
# balance: enough to find a mode, few enough that the cache stays small and
# a tactical shift is not buried under a season of history.
FORMATION_SAMPLE_SIZE = 5


@dataclass(frozen=True)
class TeamStateSnapshot:
    """One team's state at a point in time — the payload for brain.log_team_state()."""
    team: str
    league: str
    as_of: str  # YYYY-MM-DD
    manager_id: str | None
    manager_name: str | None
    manager_since: str | None
    squad_hash: str | None
    derived_formation: str | None
    source: str = "api-football.com"
    source_tier: str = "T1"
    # derived_flag: squad_hash and formation are derived (computed from source
    # data, not fetched directly). manager fields are direct (fetched verbatim).
    derived_flag: int = 1

    @property
    def has_derived_only(self) -> bool:
        """True if ONLY derived fields are present (no manager info).

        Used by callers to decide whether a snapshot is worth persisting — a
        row with nothing but None is NO DATA in a different shape (HR35)."""
        return (self.manager_name is None and self.squad_hash is None
                and self.derived_formation is None)


def _key() -> str:
    k = os.environ.get("API_FOOTBALL_KEY")
    if not k:
        raise RuntimeError("API_FOOTBALL_KEY not set — cannot fetch team-state")
    return k


def _season_for_date(d: date) -> int:
    """api-football season year for a date (same logic as full_slate)."""
    return d.year if d.month >= 7 else d.year - 1


def _is_season_accessible(season: int) -> bool:
    if season <= FREE_TIER_LAST_SEASON:
        return True
    return api_football_plan.is_paid_plan()


def _cache_dir(subdir: str) -> Path:
    d = CACHE_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cached(path: Path, max_age: float) -> dict | None:
    """Read a cached JSON payload if fresh (< max_age seconds)."""
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - blob.get("cached_at", 0) < max_age:
            return blob.get("data")
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _write_cache(path: Path, data: dict) -> None:
    try:
        path.write_text(
            json.dumps({"data": data, "cached_at": time.time()}),
            encoding="utf-8")
    except OSError:
        pass  # cache write failure is never a fetch failure


# ---- Manager / Coach --------------------------------------------------------
def fetch_manager(team_name: str, league: str,
                  api_team_id: int | None = None,
                  use_cache: bool = True) -> tuple[str | None, str | None, str | None]:
    """Fetch the current manager/coach for a team.

    Returns (manager_id, manager_name, manager_since). All None if no data.
    Uses /coaches?team={id} when the api-football team ID is available;
    falls back to /coaches?search={name} otherwise (less precise, may match
    multiple coaches).

    Raises SourceNoData if the season is beyond the plan gate."""
    if requests is None:
        raise RuntimeError("requests not installed")

    tid = api_team_id or _resolve_team_id(team_name, league)
    if tid is None:
        raise SourceNoData(f"no api-football team ID for '{team_name}' in '{league}'")

    # /coaches has no season param, so it's available on all plans. Still
    # guard with a generous cache (7 days — managers don't change daily).
    cache_dir = _cache_dir("coaches")
    cache = cache_dir / f"team_{tid}.json"
    payload = _cached(cache, 7 * 24 * 3600) if use_cache else None

    if payload is None:
        r = get_protected(
            f"{API_BASE}/coaches", breaker_name="api_football",
            headers={"x-apisports-key": _key()},
            params={"team": tid},
            timeout=30)
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"API-Football /coaches: {payload['errors']}")
        _write_cache(cache, payload)

    coaches = payload.get("response", [])
    if not coaches:
        return None, None, None

    # /coaches returns an array; pick the first as the current coach.
    # API-Football does not always mark "current", but the first result is the
    # most recent. The `career` array has start/end dates; the last entry with
    # no end date is the current appointment.
    c = coaches[0]
    name = c.get("name")
    cid = str(c.get("id")) if c.get("id") else None
    since = None
    career = c.get("career") or []
    if career:
        last = career[-1]
        since = last.get("start")
    return cid, name, since


# ---- Squad hash -------------------------------------------------------------
def fetch_squad_hash(team_name: str, league: str,
                     api_team_id: int | None = None,
                     use_cache: bool = True) -> str | None:
    """Fetch the current squad and return a hash of its composition.

    Uses /players/squads?team={id} which returns the current squad list. The
    hash is a sha1 of sorted player IDs — a change in squad composition (transfer
    window, injury recall) changes the hash, so the brain can detect turnover
    without storing 30+ player rows per team."""
    if requests is None:
        raise RuntimeError("requests not installed")

    tid = api_team_id or _resolve_team_id(team_name, league)
    if tid is None:
        raise SourceNoData(f"no api-football team ID for '{team_name}' in '{league}'")

    cache_dir = _cache_dir("squads")
    # Squad hash: cache for 24h (transfer windows change it; mid-week is stable)
    cache = cache_dir / f"squad_{tid}.json"
    payload = _cached(cache, 24 * 3600) if use_cache else None

    if payload is None:
        r = get_protected(
            f"{API_BASE}/players/squads", breaker_name="api_football",
            headers={"x-apisports-key": _key()},
            params={"team": tid},
            timeout=30)
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"API-Football /players/squads: {payload['errors']}")
        _write_cache(cache, payload)

    players = payload.get("response", [])
    if not players:
        return None

    # Hash the sorted list of player IDs. A deterministic composition fingerprint.
    player_ids = sorted(str(p.get("id", "")) for p in players)
    h = hashlib.sha1()
    for pid in player_ids:
        h.update(f"{pid}\n".encode("utf-8"))
    return h.hexdigest()[:16]  # 16 chars is plenty for change detection


# ---- Derived formation ------------------------------------------------------
def fetch_derived_formation(team_name: str, league: str,
                            api_team_id: int | None = None,
                            season: int | None = None,
                            use_cache: bool = True) -> str | None:
    """Derive the team's most common formation from recent match lineups.

    Scans the last FORMATION_SAMPLE_SIZE fixtures with lineups, extracts each
    formation string (e.g. "4-3-3"), and returns the mode. This is a DERIVED
    field (◇ in ID403) — computed from lineup data, not fetched directly.

    Returns None if no lineups are available (HR35: not guessed).

    Raises SourceNoData if the season is beyond the plan gate."""
    if requests is None:
        raise RuntimeError("requests not installed")

    tid = api_team_id or _resolve_team_id(team_name, league)
    if tid is None:
        raise SourceNoData(f"no api-football team ID for '{team_name}' in '{league}'")

    if season is None:
        season = _season_for_date(date.today())
    if not _is_season_accessible(season):
        raise SourceNoData(
            f"season {season} for '{team_name}' is beyond the free plan "
            f"(ends {FREE_TIER_LAST_SEASON}).")

    # Step 1: get recent fixtures for this team in this season
    cache_dir = _cache_dir("lineups")
    fx_cache = cache_dir / f"fixtures_{tid}_{season}.json"
    fixtures_payload = _cached(fx_cache, 6 * 3600) if use_cache else None

    if fixtures_payload is None:
        r = get_protected(
            f"{API_BASE}/fixtures", breaker_name="api_football",
            headers={"x-apisports-key": _key()},
            params={"team": tid, "season": season, "last": FORMATION_SAMPLE_SIZE},
            timeout=30)
        fixtures_payload = r.json()
        if fixtures_payload.get("errors"):
            raise RuntimeError(f"API-Football /fixtures: {fixtures_payload['errors']}")
        _write_cache(fx_cache, fixtures_payload)

    fixture_ids = [
        item["fixture"]["id"]
        for item in fixtures_payload.get("response", [])
        if item.get("fixture", {}).get("id")
    ]
    if not fixture_ids:
        return None

    # Step 2: fetch lineups for each fixture and collect formations
    formations: list[str] = []
    for fid in fixture_ids:
        lu_cache = cache_dir / f"lineup_{fid}.json"
        lu_payload = _cached(lu_cache, 24 * 3600) if use_cache else None

        if lu_payload is None:
            try:
                r = get_protected(
                    f"{API_BASE}/fixtures/lineups", breaker_name="api_football",
                    headers={"x-apisports-key": _key()},
                    params={"fixture": fid},
                    timeout=30)
                lu_payload = r.json()
                if lu_payload.get("errors"):
                    continue  # skip this fixture, don't fail the whole derivation
                _write_cache(lu_cache, lu_payload)
            except Exception:
                continue

        # Find the lineup for OUR team (match on team ID or name)
        for lu in lu_payload.get("response", []):
            lu_team = lu.get("team", {})
            if lu_team.get("id") == tid or _fuzzy_team_match(
                    lu_team.get("name", ""), team_name):
                formation = lu.get("formation")
                if formation:
                    formations.append(formation)
                break

    if not formations:
        return None

    # Mode — most common formation across the sample
    return Counter(formations).most_common(1)[0][0]


# ---- Team ID resolution -----------------------------------------------------
def _resolve_team_id(team_name: str, league: str) -> int | None:
    """Resolve a team name to an api-football team ID.

    Uses the /teams?search={name} endpoint. This is a best-effort search; the
    caller should prefer passing api_team_id directly when known (e.g. from a
    prior /fixtures call). Caches for 30 days (team IDs are stable).
    """
    if requests is None:
        return None

    cache_dir = _cache_dir("teams")
    safe = team_name.replace(" ", "_")[:40]
    cache = cache_dir / f"search_{safe}.json"
    payload = _cached(cache, 30 * 24 * 3600)

    if payload is None:
        try:
            r = get_protected(
                f"{API_BASE}/teams", breaker_name="api_football",
                headers={"x-apisports-key": _key()},
                params={"search": team_name[:20]},
                timeout=30)
            payload = r.json()
            if payload.get("errors"):
                return None
            _write_cache(cache, payload)
        except Exception:
            return None

    # Pick the first result (most relevant)
    teams = payload.get("response", [])
    if not teams:
        return None
    return teams[0].get("team", {}).get("id")


def _fuzzy_team_match(api_name: str, our_name: str) -> bool:
    """Loose team-name match for lineup team identification.

    Accent- and case-folded substring match. 'FC Copenhagen' matches
    'Copenhagen' and vice versa."""
    import unicodedata
    def fold(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s)
                       if unicodedata.category(c) != "Mn").lower()
    a, b = fold(api_name), fold(our_name)
    return a in b or b in a


# ---- Orchestration ----------------------------------------------------------
def fetch_team_state(team: str, league: str, as_of: date | None = None,
                     api_team_id: int | None = None,
                     use_cache: bool = True) -> TeamStateSnapshot:
    """Fetch a full team-state snapshot for one team.

    Calls all three sub-fetchers (manager, squad, formation) and assembles
    a TeamStateSnapshot. Individual sub-failures leave the field as None
    (HR35: never guessed, never blocks the other fields). Raises SourceNoData
    only if the season is inaccessible (gating failure, not a data gap).

    Args:
        team: model-key team name.
        league: league name (for provenance + ID resolution context).
        as_of: date this snapshot represents (default: today).
        api_team_id: api-football team ID if known (avoids a search call).
        use_cache: use cached payloads.
    """
    if as_of is None:
        as_of = date.today()
    as_of_str = as_of.isoformat()

    # Manager (direct fetch)
    mgr_id = mgr_name = mgr_since = None
    try:
        mgr_id, mgr_name, mgr_since = fetch_manager(
            team, league, api_team_id=api_team_id, use_cache=use_cache)
    except SourceNoData:
        raise  # season gate — propagate
    except Exception:
        pass  # a sub-fetch failure is a None field, not a snapshot failure

    # Squad hash (direct fetch, then hashed = derived)
    squad_hash = None
    try:
        squad_hash = fetch_squad_hash(
            team, league, api_team_id=api_team_id, use_cache=use_cache)
    except SourceNoData:
        raise
    except Exception:
        pass

    # Formation (fully derived from lineups)
    formation = None
    try:
        formation = fetch_derived_formation(
            team, league, api_team_id=api_team_id, use_cache=use_cache)
    except SourceNoData:
        # formation is best-effort: if the season gate blocks it, leave None
        # but don't propagate — the manager + squad might still be accessible.
        pass
    except Exception:
        pass

    snap = TeamStateSnapshot(
        team=team, league=league, as_of=as_of_str,
        manager_id=mgr_id, manager_name=mgr_name, manager_since=mgr_since,
        squad_hash=squad_hash, derived_formation=formation)

    if snap.has_derived_only:
        raise SourceNoData(
            f"no team-state data for '{team}' in '{league}' — all fields None")

    return snap


def fetch_league_team_states(league: str, as_of: date | None = None,
                             use_cache: bool = True
                             ) -> tuple[list[TeamStateSnapshot], list[str]]:
    """Fetch team-state for every team in a league.

    Uses /teams?league={id}&season={year} to enumerate the league's teams, then
    calls fetch_team_state() for each. Returns (snapshots, flags). Individual
    team failures go into flags, never raising."""
    if requests is None:
        raise RuntimeError("requests not installed")

    league_id = get_api_football_id(league)
    if league_id is None:
        raise SourceNoData(f"'{league}' has no api-football league ID")

    if as_of is None:
        as_of = date.today()
    season = _season_for_date(as_of)
    if not _is_season_accessible(season):
        raise SourceNoData(
            f"season {season} for '{league}' is beyond the free plan")

    # Enumerate teams in the league
    cache_dir = _cache_dir("teams")
    cache = cache_dir / f"league_{league_id}_{season}.json"
    payload = _cached(cache, 24 * 3600) if use_cache else None

    if payload is None:
        r = get_protected(
            f"{API_BASE}/teams", breaker_name="api_football",
            headers={"x-apisports-key": _key()},
            params={"league": league_id, "season": season},
            timeout=30)
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"API-Football /teams: {payload['errors']}")
        _write_cache(cache, payload)

    teams = payload.get("response", [])
    snapshots: list[TeamStateSnapshot] = []
    flags: list[str] = []

    for entry in teams:
        tid = entry.get("team", {}).get("id")
        name = entry.get("team", {}).get("name")
        if not tid or not name:
            continue
        try:
            snap = fetch_team_state(name, league, as_of=as_of,
                                    api_team_id=tid, use_cache=use_cache)
            snapshots.append(snap)
        except SourceNoData as e:
            flags.append(f"{name}: {e}")
        except Exception as e:
            flags.append(f"{name}: team-state fetch failed ({str(e)[:60]})")

    return snapshots, flags
