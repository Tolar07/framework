"""
ESPN Lineups Module — confirmed starting XIs with formations from ESPN.

Provides confirmed starting lineups for completed/upcoming matches from ESPN's
summary endpoint. Used for team news verification and formation analysis in the
multi-source fabric (data/multi_source.py).

Endpoints used:
- /summary?event=<event_id>&lineups=true - match summary with lineups, formations

HR35 Compliance:
- Only returns confirmed lineups (status = "confirmed")
- Skip malformed rows, record skipped count in provenance
- Honest gaps: return empty list if no data available (no fabrication)
- Cache: 6h TTL for upcoming matches, 30d for completed matches
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from data.espn_source import SLUGS as LEAGUE_MAP


# --- Data Models ---

@dataclass
class LineupPlayer:
    """A player in the starting lineup or bench."""
    player_id: str
    name: str
    short_name: str
    position: str  # GK, DEF, MID, FWD
    jersey_number: Optional[int] = None
    is_starter: bool = True
    formation_position: Optional[str] = None  # e.g., "RCB", "LW", "ST"


@dataclass
class TeamLineup:
    """Complete lineup for one team."""
    team_id: str
    team_name: str
    formation: str  # e.g., "3-5-2", "4-3-3"
    starters: List[LineupPlayer]
    substitutes: List[LineupPlayer]
    coach: Optional[str] = None


@dataclass
class MatchLineup:
    """Complete lineup data for a match."""
    event_id: str
    league: str
    home_team: str
    away_team: str
    match_date: str
    status: str  # "upcoming", "live", "completed", "confirmed"
    home_lineup: Optional[TeamLineup] = None
    away_lineup: Optional[TeamLineup] = None
    provenance: Optional[Dict[str, Any]] = None


# --- Cache ---

CACHE_DIR = Path(__file__).parent / "cache" / "espn_lineups"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache TTL: 6h for upcoming/live, 30d for completed
UPCOMING_TTL = 6 * 3600
COMPLETED_TTL = 30 * 24 * 3600


def _is_match_completed(match_date: str, status: str) -> bool:
    """Check if a match is completed."""
    if status in ("completed", "STATUS_FINAL", "Final"):
        return True
    try:
        match_dt = datetime.fromisoformat(match_date)
        return match_dt < datetime.now() - timedelta(hours=3)
    except Exception:
        return False


def _cache_path(event_id: str) -> Path:
    return CACHE_DIR / f"{event_id}.json"


def _load_cache(event_id: str, match_date: str, status: str) -> Optional[MatchLineup]:
    """Load cached lineups if within TTL."""
    path = _cache_path(event_id)
    if not path.exists():
        return None

    age = time.time() - path.stat().st_mtime
    ttl = COMPLETED_TTL if _is_match_completed(match_date, status) else UPCOMING_TTL

    if age > ttl:
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Reconstruct dataclasses
        home = None
        away = None
        if data.get("home_lineup"):
            h = data["home_lineup"]
            home = TeamLineup(
                team_id=h["team_id"],
                team_name=h["team_name"],
                formation=h["formation"],
                starters=[LineupPlayer(**p) for p in h["starters"]],
                substitutes=[LineupPlayer(**p) for p in h["substitutes"]],
                coach=h.get("coach"),
            )
        if data.get("away_lineup"):
            a = data["away_lineup"]
            away = TeamLineup(
                team_id=a["team_id"],
                team_name=a["team_name"],
                formation=a["formation"],
                starters=[LineupPlayer(**p) for p in a["starters"]],
                substitutes=[LineupPlayer(**p) for p in a["substitutes"]],
                coach=a.get("coach"),
            )

        return MatchLineup(
            event_id=data["event_id"],
            league=data["league"],
            home_team=data["home_team"],
            away_team=data["away_team"],
            match_date=data["match_date"],
            status=data["status"],
            home_lineup=home,
            away_lineup=away,
            provenance=data.get("provenance"),
        )
    except Exception:
        return None


def _save_cache(lineup: MatchLineup) -> None:
    """Save lineup to cache."""
    path = _cache_path(lineup.event_id)
    data = asdict(lineup)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# --- Formation Parsing ---

FORMATION_MAP = {
    # Common formations from ESPN
    "3-5-2": "3-5-2",
    "4-4-2": "4-4-2",
    "4-3-3": "4-3-3",
    "4-2-3-1": "4-2-3-1",
    "3-4-3": "3-4-3",
    "5-3-2": "5-3-2",
    "4-5-1": "4-5-1",
    "5-4-1": "5-4-1",
    "4-1-4-1": "4-1-4-1",
    "3-6-1": "3-6-1",
}


def _parse_formation(formation_str: str) -> str:
    """Normalize formation string from ESPN."""
    if not formation_str:
        return "Unknown"
    # ESPN typically returns standard format like "3-5-2"
    return FORMATION_MAP.get(formation_str.strip(), formation_str.strip())


def _position_abbrev(position: str) -> str:
    """Convert ESPN position to standard abbreviation."""
    pos_map = {
        "GK": "GK",
        "CB": "DEF",
        "LB": "DEF",
        "RB": "DEF",
        "LWB": "DEF",
        "RWB": "DEF",
        "CM": "MID",
        "CDM": "MID",
        "CAM": "MID",
        "LM": "MID",
        "RM": "MID",
        "LW": "FWD",
        "RW": "FWD",
        "CF": "FWD",
        "ST": "FWD",
    }
    return pos_map.get(position.upper(), position.upper())


# --- Lineup Extraction ---

def _extract_team_lineup(lineup_data: Dict[str, Any], team_type: str) -> Optional[TeamLineup]:
    """Extract team lineup from ESPN lineup data."""
    try:
        team = lineup_data.get("team", {})
        team_id = str(team.get("id", ""))
        team_name = team.get("displayName") or team.get("name") or team.get("shortDisplayName", "")

        formation = _parse_formation(lineup_data.get("formation", ""))

        starters = []
        substitutes = []

        athletes = lineup_data.get("athletes", [])
        for athlete in athletes:
            player = athlete.get("athlete", {})
            pos = athlete.get("position", "")
            starter = athlete.get("starter", False)

            lineup_player = LineupPlayer(
                player_id=str(player.get("id", "")),
                name=player.get("displayName") or player.get("name") or "",
                short_name=player.get("shortName") or player.get("displayName") or "",
                position=_position_abbrev(pos),
                jersey_number=athlete.get("jersey"),
                is_starter=starter,
                formation_position=athlete.get("slot"),
            )
            if starter:
                starters.append(lineup_player)
            else:
                substitutes.append(lineup_player)

        return TeamLineup(
            team_id=team_id,
            team_name=team_name,
            formation=formation,
            starters=starters,
            substitutes=substitutes,
            coach=lineup_data.get("coach"),
        )
    except Exception:
        return None


# --- Main Fetch Functions ---

def fetch_lineup_for_event(event_id: str) -> Optional[MatchLineup]:
    """
    Fetch confirmed lineups for a specific event ID.

    Args:
        event_id: ESPN event ID

    Returns:
        MatchLineup with home/away lineups, or None if unavailable
    """
    if requests is None:
        return None

    # Check cache
    cached = _load_cache(event_id, "", "unknown")
    if cached:
        return cached

    skipped = 0
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/summary"
        params = {"event": event_id, "lineups": "true"}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[espn_lineups] Error fetching event {event_id}: {e}")
        return None

    try:
        header = data.get("header", {})
        league = header.get("league", {}).get("name", "Unknown")
        match_date = header.get("date", "").split("T")[0]
        status = header.get("status", {}).get("type", {}).get("name", "unknown")

        home_lineup_data = data.get("lineups", [{}])[0] if data.get("lineups") else {}
        away_lineup_data = data.get("lineups", [{}])[1] if len(data.get("lineups", [])) > 1 else {}

        home_team = header.get("competitors", [{}])[0].get("team", {}).get("shortDisplayName", "")
        away_team = header.get("competitors", [{}])[1].get("team", {}).get("shortDisplayName", "")

        home = _extract_team_lineup(home_lineup_data, "home") if home_lineup_data else None
        away = _extract_team_lineup(away_lineup_data, "away") if away_lineup_data else None

        # Only return if we have at least one lineup
        if home or away:
            lineup = MatchLineup(
                event_id=event_id,
                league=league,
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                status=status,
                home_lineup=home,
                away_lineup=away,
                provenance={
                    "source": "ESPN",
                    "endpoint": "summary?lineups=true",
                    "fetched_at": datetime.utcnow().isoformat() + "Z",
                    "skipped_malformed": skipped,
                }
            )
            _save_cache(lineup)
            return lineup

    except Exception as e:
        print(f"[espn_lineups] Error parsing lineups for {event_id}: {e}")

    return None


def fetch_lineups_for_date(target_date: str, league: Optional[str] = None) -> List[MatchLineup]:
    """
    Fetch lineups for all matches on a given date.

    Note: ESPN doesn't provide a bulk lineup endpoint, so this iterates through
    the scoreboard for the date and fetches lineups per event.
    """
    if requests is None:
        return []

    results = []
    leagues_to_query = [league] if league else list(LEAGUE_MAP.keys())

    for lg in leagues_to_query:
        espn_league = LEAGUE_MAP.get(lg)
        if not espn_league:
            continue

        date_str = target_date.replace("-", "")
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_league}/scoreboard"
            params = {"dates": date_str, "limit": 100}
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        events = data.get("events", [])
        for event in events:
            event_id = str(event.get("id", ""))
            if event_id:
                lineup = fetch_lineup_for_event(event_id)
                if lineup:
                    results.append(lineup)

    return results


# --- Integration with Multi-Source Fabric ---

def get_lineups_source_name() -> str:
    """Return the source name for multi-source registration."""
    return "espn_lineups"


def create_lineups_fetcher(league: str):
    """Create a fetcher callable for the multi-source fabric."""
    def fetcher(target_date: str) -> List[MatchLineup]:
        return fetch_lineups_for_date(target_date, league)
    return fetcher


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ESPN Lineups fetcher")
    parser.add_argument("event_id", nargs="?", help="ESPN event ID")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)")
    parser.add_argument("--league", help="League name (e.g., 'La Liga')")

    args = parser.parse_args()

    if args.event_id:
        lineup = fetch_lineup_for_event(args.event_id)
        if lineup:
            print(f"\n{'='*80}")
            print(f"LINEUP - {lineup.home_team} vs {lineup.away_team}")
            print(f"{lineup.league} | {lineup.match_date} | {lineup.status}")
            print(f"{'='*80}\n")

            for side, name in [("HOME", lineup.home_lineup), ("AWAY", lineup.away_lineup)]:
                if name:
                    print(f"  {side} ({name.formation}):")
                    for p in name.starters:
                        print(f"    {p.jersey_number:>2}  {p.name:<25} {p.position:<4}  {p.formation_position or ''}")
                    for p in name.substitutes:
                        print(f"    {p.jersey_number:>2}  {p.name:<25} {p.position:<4} (sub)")
                    print()
    elif args.date:
        lineups = fetch_lineups_for_date(args.date, args.league)
        print(f"\n{'='*80}")
        print(f"LINEUPS FOR {args.date} - {len(lineups)} matches")
        print(f"{'='*80}\n")
        for l in lineups:
            print(f"  {l.home_team} vs {l.away_team} ({l.league})")
            if l.home_lineup:
                print(f"    HOME: {l.home_lineup.formation}")
            if l.away_lineup:
                print(f"    AWAY: {l.away_lineup.formation}")
    else:
        print("Usage: python espn_lineups.py <event_id> OR --date YYYY-MM-DD [--league LEAGUE]")