"""
Dynamic league registry — single source of truth for league eligibility and per-source IDs.

Replaces the hardcoded WHITELISTED_LEAGUES + four parallel ID dicts.
Each league entry carries per-source IDs so new leagues are added by editing
config/leagues.json, not four Python modules.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).parent.parent / "config" / "leagues.json"


class LeagueConfig:
    """Per-league configuration loaded from leagues.json."""

    def __init__(self, data: dict[str, Any]):
        self.name: str = data["name"]
        self.country: str = data.get("country", "")
        self.tier: int = data.get("tier", 1)
        self.type: str = data.get("type", "club")  # "club" or "national"
        self.ids: dict[str, Any] = data.get("ids", {})
        self.sources: dict[str, str] = data.get("sources", {})
        self.aliases: dict[str, str] = data.get("aliases", {})
        self.deploy_eligible: bool = data.get("deploy_eligible", True)
        self.scan_only: bool = data.get("scan_only", False)

    def get_id(self, source: str) -> Any:
        """Get ID for a specific source, or None if not configured."""
        return self.ids.get(source)

    @property
    def thesportsdb_id(self) -> int | None:
        v = self.ids.get("thesportsdb")
        return int(v) if v is not None else None

    @property
    def odds_api_key(self) -> str | None:
        return self.ids.get("odds_api")

    @property
    def api_football_id(self) -> int | None:
        v = self.ids.get("api_football")
        return int(v) if v is not None else None

    @property
    def football_data_code(self) -> str | None:
        return self.ids.get("football_data")


class LeagueRegistry:
    """Singleton registry loaded from config/leagues.json at import time."""

    _instance: LeagueRegistry | None = None
    _leagues: dict[str, LeagueConfig]

    def __new__(cls) -> LeagueRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._leagues = cls._instance._load()
        return cls._instance

    def _load(self) -> dict[str, LeagueConfig]:
        if not CONFIG_PATH.exists():
            raise RuntimeError(f"League config not found at {CONFIG_PATH}")
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        out: dict[str, LeagueConfig] = {}
        for item in raw.get("leagues", []):
            cfg = LeagueConfig(item)
            out[cfg.name] = cfg
        if not out:
            raise RuntimeError(f"No leagues found in {CONFIG_PATH}")
        return out

    def get(self, name: str) -> LeagueConfig | None:
        """Get config by exact league name."""
        return self._leagues.get(name)

    def get_ids(self, name: str) -> dict[str, Any] | None:
        """Get ID dict for a league, or None if unknown."""
        cfg = self._leagues.get(name)
        return cfg.ids if cfg else None

    def is_eligible(self, name: str) -> bool:
        """Check if league is deploy-eligible (replaces is_deploy_eligible)."""
        cfg = self._leagues.get(name)
        return cfg is not None and cfg.deploy_eligible

    def all_leagues(self) -> list[str]:
        """All league names in registry order (seeded order in JSON)."""
        return list(self._leagues.keys())

    def deploy_eligible_leagues(self) -> list[str]:
        """Only deploy-eligible leagues (for shortlist/gate)."""
        return [name for name, cfg in self._leagues.items() if cfg.deploy_eligible]

    def scan_leagues(self) -> list[str]:
        """Leagues to scan (scan_only + deploy_eligible)."""
        return [name for name, cfg in self._leagues.items() if not cfg.scan_only or cfg.deploy_eligible]

    def __contains__(self, name: str) -> bool:
        return name in self._leagues

    def __len__(self) -> int:
        return len(self._leagues)

    def __iter__(self):
        return iter(self._leagues)

    # Backward-compat: WHITELISTED_LEAGUES derived from registry
    @property
    def WHITELISTED_LEAGUES(self) -> list[str]:
        """Derived whitelist — all deploy-eligible leagues, kept sorted for stable ordering."""
        return sorted(self.deploy_eligible_leagues())


# Global instance (import-time load)
registry = LeagueRegistry()


# Convenience functions for source modules (no registry import needed)
def get_thesportsdb_id(league: str) -> int | None:
    cfg = registry.get(league)
    return cfg.thesportsdb_id if cfg else None


def get_odds_api_key(league: str) -> str | None:
    cfg = registry.get(league)
    return cfg.odds_api_key if cfg else None


def get_api_football_id(league: str) -> int | None:
    cfg = registry.get(league)
    return cfg.api_football_id if cfg else None


def get_football_data_code(league: str) -> str | None:
    cfg = registry.get(league)
    return cfg.football_data_code if cfg else None