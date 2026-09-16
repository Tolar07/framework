"""
API configuration for OLP XDV
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class APIConfig:
    """API-related configuration parameters."""

    # API credentials (loaded from environment, not stored in config files)
    odds_api_key: str = field(default_factory=lambda: os.getenv("ODDS_API_KEY", ""))
    api_football_key: str = field(default_factory=lambda: os.getenv("APIFOOTBALL_KEY", ""))
    the_sports_db_key: str = field(default_factory=lambda: os.getenv("THE_SPORTS_DB_KEY", ""))
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: Optional[int] = field(default_factory=lambda:
        int(os.getenv("TELEGRAM_CHAT_ID", "0")) if os.getenv("TELEGRAM_CHAT_ID", "0") != "0" else None)

    # API endpoint configurations
    odds_api: Dict[str, Any] = field(default_factory=lambda: {
        "base_url": "https://api.the-odds-api.com",
        "timeout": 30,
        "max_retries": 3,
        "retry_backoff_factor": 0.5
    })

    api_football: Dict[str, Any] = field(default_factory=lambda: {
        "base_url": "https://v3.football.api-sports.io",
        "timeout": 30,
        "max_retries": 3,
        "retry_backoff_factor": 0.5,
        "rate_limit_per_minute": 100
    })

    the_sports_db: Dict[str, Any] = field(default_factory=lambda: {
        "base_url": "https://www.thesportsdb.com/api/v1/json",
        "timeout": 30,
        "max_retries": 3,
        "retry_backoff_factor": 0.5
    })

    espn: Dict[str, Any] = field(default_factory=lambda: {
        "base_url": "https://site.api.espn.com/apis/site/v2/sports",
        "timeout": 30,
        "max_retries": 3,
        "retry_backoff_factor": 0.5
    })

    telegram: Dict[str, Any] = field(default_factory=lambda: {
        "base_url": "https://api.telegram.org/bot",
        "timeout": 30,
        "max_retries": 3,
        "retry_backoff_factor": 0.5
    })

    global_settings: Dict[str, Any] = field(default_factory=lambda: {
        "user_agent": "OLP-XDV/1.0",
        "max_concurrent_requests": 10,
        "request_timeout": 30
    })

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive keys)."""
        return {
            "odds_api": self.odds_api,
            "api_football": self.api_football,
            "the_sports_db": self.the_sports_db,
            "espn": self.espn,
            "telegram": self.telegram,
            "global": self.global_settings
            # Note: API keys are not included in to_dict for security
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIConfig":
        """Create configuration from dictionary."""
        return cls(
            odds_api_key="",  # Will be loaded from environment
            api_football_key="",  # Will be loaded from environment
            the_sports_db_key="",  # Will be loaded from environment
            telegram_bot_token="",  # Will be loaded from environment
            telegram_chat_id=None,  # Will be loaded from environment
            odds_api=data.get("odds_api", {}),
            api_football=data.get("api_football", {}),
            the_sports_db=data.get("the_sports_db", {}),
            espn=data.get("espn", {}),
            telegram=data.get("telegram", {}),
            global_settings=data.get("global", {})
        )