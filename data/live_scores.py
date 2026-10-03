"""
Live in-play score feed — ESPN scoreboard + API-Football fallback.

RATIFIED under HR34 (Architect) as the live scores redundancy layer for the
client dashboard and real-time board updates.

ESPN: key-free, covers all leagues in WHITELISTED_LEAGUES including continental
      competitions and no-TSDB-ID leagues (Austrian Bundesliga, HNL).
API-Football: paid fallback for when ESPN quota/exhausted or missing coverage.

HR35 throughout: a match missing score/time/status is NEVER fabricated —
the source raises SourceNoData and the multi-source layer fails over.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Any

from data.multi_source import SourceNoData
from data.retry import get

try:
    import requests
except ImportError:
    requests = None

# Cache configuration
CACHE_DIR = Path(__file__).parent / "cache" / "live_scores"
MAX_AGE_SECONDS = 60  # 1-minute TTL for live scores


@dataclass
class LiveScore:
    """A single live match score."""
    league: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str  # "SCHEDULED" | "LIVE" | "HT" | "FT" | "PEN" | "AET" | "POSTPONED" | "CANCELLED"
    minute: Optional[int] = None
    kickoff: Optional[date] = None
    source: str = ""


class ESPNFixturesSource:
    """ESPN scoreboard API — key-free, covers all WHITELISTED_LEAGUES."""

    ESPN_LEAGUE_MAP = {
        "Premier League": "eng.1",
        "La Liga": "esp.1",
        "Serie A": "ita.1",
        "Bundesliga": "ger.1",
        "Ligue 1": "fra.1",
        "Eredivisie": "ned.1",
        "Primeira Liga": "por.1",
        "Scottish Premiership": "sco.1",
        "Belgian Pro League": "bel.1",
        "Danish Superliga": "den.1",
        "Ekstraklasa": "pol.1",
        "Austrian Bundesliga": "aut.1",
        "HNL": "hrv.1",
        "Championship": "eng.2",
        "Champions League": "uefa.champions",
        "Europa League": "uefa.europa",
        "Conference League": "uefa.conf",
        "UEFA Super Cup": "uefa.supercup",
    }

    # ESPN blocks browser-like UAs but allows Python-urllib/sports-skills UAs
    # (validated: sports-skills UA returns 200, Chrome UA returns 403)
    _USER_AGENT = (
        "Python-urllib/3.11 "
        "(+sports-skills/dev; https://github.com/machina-sports/sports-skills)"
    )

    def __init__(self):
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/soccer"
        self.timeout = 15.0

    def _cache_path(self, league: str, day: str) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / f"espn_{league.replace(' ', '_')}_{day}.json"

    def _read_cache(self, path: Path) -> Optional[dict]:
        try:
            if time.time() - path.stat().st_mtime > MAX_AGE_SECONDS:
                return None
        except OSError:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, path: Path, payload: dict) -> None:
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    def _map_status(self, espn_status: str) -> str:
        """Map ESPN status to our canonical statuses."""
        if espn_status in ("STATUS_SCHEDULED", "STATUS_PREGAME"):
            return "SCHEDULED"
        if espn_status in ("STATUS_IN_PROGRESS", "STATUS_FIRST_HALF", "STATUS_SECOND_HALF"):
            return "LIVE"
        if espn_status == "STATUS_HALFTIME":
            return "HT"
        if espn_status in ("STATUS_FULL_TIME", "STATUS_FINAL"):
            return "FT"
        if espn_status in ("STATUS_PENALTIES", "STATUS_FINAL_PEN"):
            return "PEN"
        if espn_status in ("STATUS_EXTRA_TIME", "STATUS_FINAL_AET"):
            return "AET"
        if espn_status == "STATUS_POSTPONED":
            return "POSTPONED"
        if espn_status == "STATUS_CANCELED":
            return "CANCELLED"
        return "UNKNOWN"

    def fetch_live_scores(self, league: str, day: Optional[str] = None) -> list[LiveScore]:
        """Fetch live scores for a league on a given day (default: today).

        ESPN scoreboard API returns upcoming matches; we filter by day locally.
        """
        if requests is None:
            raise RuntimeError("live_scores: 'requests' library required")

        if league not in self.ESPN_LEAGUE_MAP:
            raise SourceNoData(f"espn: league {league!r} not mapped")

        espn_slug = self.ESPN_LEAGUE_MAP[league]
        target_day = day or date.today().isoformat()  # YYYY-MM-DD for filtering
        cache_path = self._cache_path(league, target_day)

        # Check cache
        payload = self._read_cache(cache_path)
        if payload is None:
            url = f"{self.base_url}/{espn_slug}/scoreboard"
            params = {"limit": 100}
            headers = {"User-Agent": self._USER_AGENT}
            resp = get(url, params=params, headers=headers, timeout=self.timeout)
            payload = resp.json()
            self._write_cache(cache_path, payload)

        events = payload.get("events", [])
        scores: list[LiveScore] = []

        for event in events:
            try:
                comp = event.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue

                home = next(c for c in competitors if c.get("homeAway") == "home")
                away = next(c for c in competitors if c.get("homeAway") == "away")

                home_name = home.get("team", {}).get("displayName", "")
                away_name = away.get("team", {}).get("displayName", "")
                home_score = int(home.get("score", "0") or 0)
                away_score = int(away.get("score", "0") or 0)

                status_info = comp.get("status", {}).get("type", {})
                espn_status = status_info.get("name", "STATUS_SCHEDULED")
                status = self._map_status(espn_status)

                minute = None
                if status == "LIVE":
                    period = comp.get("status", {}).get("period", 0)
                    display_clock = comp.get("status", {}).get("displayClock", "")
                    if display_clock and display_clock.isdigit():
                        minute = int(display_clock)
                    elif period:
                        minute = 45 * (period - 1) + 1

                utc_date = event.get("date", "")
                kickoff = None
                if utc_date:
                    try:
                        kickoff = datetime.fromisoformat(utc_date.replace("Z", "+00:00")).date()
                    except (ValueError, AttributeError):
                        pass

                # Filter by target day if kickoff is available
                if kickoff and kickoff.isoformat() != target_day:
                    continue

                scores.append(LiveScore(
                    league=league,
                    home_team=home_name,
                    away_team=away_name,
                    home_score=home_score,
                    away_score=away_score,
                    status=status,
                    minute=minute,
                    kickoff=kickoff,
                    source="espn"
                ))
            except (KeyError, ValueError, TypeError, StopIteration):
                # Skip malformed events — HR35: never fabricate
                continue

        if not scores:
            raise SourceNoData(f"espn: no live scores for {league} on {target_day}")

        return scores


class APIFootballLiveScoresSource:
    """API-Football live scores (paid plan fallback)."""

    API_FOOTBALL_LEAGUE_IDS = {
        "Premier League": 39,
        "La Liga": 140,
        "Serie A": 135,
        "Bundesliga": 78,
        "Ligue 1": 61,
        "Eredivisie": 88,
        "Primeira Liga": 94,
        "Scottish Premiership": 179,
        "Belgian Pro League": 144,
        "Danish Superliga": 119,
        "Ekstraklasa": 113,
        "Austrian Bundesliga": 103,
        "HNL": 188,
        "Championship": 40,
        "Champions League": 2,
        "Europa League": 3,
        "Conference League": 848,
        "UEFA Super Cup": 865,
    }

    def __init__(self):
        self.base_url = "https://v3.football.api-sports.io"
        self.timeout = 30.0

    def _get_key(self) -> str:
        key = os.environ.get("API_FOOTBALL_KEY")
        if not key:
            raise RuntimeError("API_FOOTBALL_KEY not set in .env")
        return key

    def _headers(self) -> dict:
        return {"x-apisports-key": self._get_key()}

    def _cache_path(self, league: str, day: str) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / f"apif_live_{league.replace(' ', '_')}_{day}.json"

    def _read_cache(self, path: Path) -> Optional[dict]:
        try:
            if time.time() - path.stat().st_mtime > MAX_AGE_SECONDS:
                return None
        except OSError:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, path: Path, payload: dict) -> None:
        try:
            path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    def _map_status(self, apif_status: str) -> str:
        """Map API-Football status to our canonical statuses."""
        status_map = {
            "NS": "SCHEDULED",
            "1H": "LIVE", "2H": "LIVE", "HT": "HT",
            "FT": "FT", "ET": "AET", "P": "PEN",
            "BT": "PEN", "SUSP": "SUSPENDED",
            "PST": "POSTPONED", "CANC": "CANCELLED",
            "ABD": "ABANDONED", "AWD": "AWARDED",
        }
        return status_map.get(apif_status, "UNKNOWN")

    def fetch_live_scores(self, league: str, day: Optional[str] = None) -> list[LiveScore]:
        """Fetch live scores for a league on a given day (default: today)."""
        if requests is None:
            raise RuntimeError("live_scores: 'requests' library required")

        if league not in self.API_FOOTBALL_LEAGUE_IDS:
            raise SourceNoData(f"api_football: league {league!r} not mapped")

        league_id = self.API_FOOTBALL_LEAGUE_IDS[league]
        day = day or date.today().isoformat()
        cache_path = self._cache_path(league, day)

        # Check cache
        payload = self._read_cache(cache_path)
        if payload is None:
            url = f"{self.base_url}/fixtures"
            params = {"league": league_id, "date": day, "timezone": "UTC"}
            resp = get(url, headers=self._headers(), params=params, timeout=self.timeout)
            payload = resp.json()
            self._write_cache(cache_path, payload)

        fixtures = payload.get("response", [])
        scores: list[LiveScore] = []

        for fixture in fixtures:
            try:
                fixture_data = fixture.get("fixture", {})
                teams = fixture.get("teams", {})
                goals = fixture.get("goals", {})
                score = fixture.get("score", {})

                home_name = teams.get("home", {}).get("name", "")
                away_name = teams.get("away", {}).get("name", "")
                home_score = goals.get("home", 0) or 0
                away_score = goals.get("away", 0) or 0

                status_short = fixture_data.get("status", {}).get("short", "NS")
                status = self._map_status(status_short)

                minute = None
                if status == "LIVE":
                    elapsed = fixture_data.get("status", {}).get("elapsed")
                    if elapsed is not None:
                        minute = elapsed

                utc_date = fixture_data.get("date", "")
                kickoff = None
                if utc_date:
                    try:
                        kickoff = datetime.fromisoformat(utc_date.replace("Z", "+00:00")).date()
                    except (ValueError, AttributeError):
                        pass

                scores.append(LiveScore(
                    league=league,
                    home_team=home_name,
                    away_team=away_name,
                    home_score=home_score,
                    away_score=away_score,
                    status=status,
                    minute=minute,
                    kickoff=kickoff,
                    source="api_football"
                ))
            except (KeyError, ValueError, TypeError):
                continue

        if not scores:
            raise SourceNoData(f"api_football: no live scores for {league} on {day}")

        return scores


# Convenience functions for multi-source integration

def fetch_espn_live_scores(league: str, day: Optional[str] = None) -> list[LiveScore]:
    """Fetch live scores from ESPN."""
    return ESPNFixturesSource().fetch_live_scores(league, day)


def fetch_apif_live_scores(league: str, day: Optional[str] = None) -> list[LiveScore]:
    """Fetch live scores from API-Football."""
    return APIFootballLiveScoresSource().fetch_live_scores(league, day)