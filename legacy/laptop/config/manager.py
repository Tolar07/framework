"""
Configuration Manager for OLP XDV
Centralizes all configuration management with validation, defaults, and environment support.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .betting_config import BettingConfig
from .api_config import APIConfig
from .logging_config import LoggingConfig


@dataclass
class Config:
    """Main configuration container."""
    betting: BettingConfig = field(default_factory=BettingConfig)
    api: APIConfig = field(default_factory=APIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Environment detection
    environment: str = field(default_factory=lambda: os.getenv("OLP_ENV", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("OLP_DEBUG", "false").lower() == "true")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "betting": self.betting.to_dict(),
            "api": self.api.to_dict(),
            "logging": self.logging.to_dict(),
            "environment": self.environment,
            "debug": self.debug
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create configuration from dictionary."""
        return cls(
            betting=BettingConfig.from_dict(data.get("betting", {})),
            api=APIConfig.from_dict(data.get("api", {})),
            logging=LoggingConfig.from_dict(data.get("logging", {})),
            environment=data.get("environment", "development"),
            debug=data.get("debug", False)
        )


class ConfigManager:
    """Manages configuration loading, validation, and access."""

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory containing configuration files. Defaults to ./config/
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent
        self._config: Optional[Config] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from files and environment."""
        # Start with defaults
        config = Config()

        # Load from JSON files if they exist
        config_files = [
            self.config_dir / "betting_config.json",
            self.config_dir / "api_config.json",
            self.config_dir / "logging_config.json"
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        file_data = json.load(f)

                    # Update config based on file type
                    if config_file.name == "betting_config.json":
                        config.betting = BettingConfig.from_dict(file_data)
                    elif config_file.name == "api_config.json":
                        config.api = APIConfig.from_dict(file_data)
                    elif config_file.name == "logging_config.json":
                        config.logging = LoggingConfig.from_dict(file_data)

                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Failed to load config from {config_file}: {e}")

        # Override with environment variables
        config = self._apply_env_overrides(config)

        # Validate final configuration
        config = self._validate_config(config)

        self._config = config

    def _apply_env_overrides(self, config: Config) -> Config:
        """Apply environment variable overrides to configuration."""
        # Betting configuration overrides
        if os.getenv("OLP_MAX_ODDS_CAP"):
            try:
                config.betting.max_odds_cap = float(os.getenv("OLP_MAX_ODDS_CAP"))
            except ValueError:
                pass

        if os.getenv("OLP_MIN_ODDS_FLOOR"):
            try:
                config.betting.min_odds_floor = float(os.getenv("OLP_MIN_ODDS_FLOOR"))
            except ValueError:
                pass

        if os.getenv("OLP_PREFERRED_ODDS_CEILING"):
            try:
                config.betting.preferred_odds_ceiling = float(os.getenv("OLP_PREFERRED_ODDS_CEILING"))
            except ValueError:
                pass

        # API configuration overrides
        if os.getenv("ODDS_API_KEY"):
            config.api.odds_api_key = os.getenv("ODDS_API_KEY")

        if os.getenv("APIFOOTBALL_KEY"):
            config.api.api_football_key = os.getenv("APIFOOTBALL_KEY")

        if os.getenv("THE_SPORTS_DB_KEY"):
            config.api.the_sports_db_key = os.getenv("THE_SPORTS_DB_KEY")

        if os.getenv("TELEGRAM_BOT_TOKEN"):
            config.api.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

        if os.getenv("TELEGRAM_CHAT_ID"):
            try:
                config.api.telegram_chat_id = int(os.getenv("TELEGRAM_CHAT_ID"))
            except ValueError:
                pass

        # Framework configuration overrides
        if os.getenv("FRAMEWORK__SPORTYBET_MAX_ODDS"):
            try:
                config.betting.max_odds_cap = float(os.getenv("FRAMEWORK__SPORTYBET_MAX_ODDS"))
                config.betting.preferred_odds_ceiling = float(os.getenv("FRAMEWORK__SPORTYBET_MAX_ODDS"))
            except ValueError:
                pass

        # Logging configuration overrides
        if os.getenv("OLP_LOG_LEVEL"):
            config.logging.level = os.getenv("OLP_LOG_LEVEL").upper()

        if os.getenv("OLP_LOG_FILE"):
            config.logging.file_path = os.getenv("OLP_LOG_FILE")

        return config

    def _validate_config(self, config: Config) -> Config:
        """Validate configuration values."""
        # Validate betting configuration
        if config.betting.max_odds_cap <= config.betting.min_odds_floor:
            raise ValueError("max_odds_cap must be greater than min_odds_floor")

        if config.betting.preferred_odds_ceiling < config.betting.min_odds_floor:
            raise ValueError("preferred_odds_ceiling must be >= min_odds_floor")

        if config.betting.preferred_odds_ceiling > config.betting.max_odds_cap:
            raise ValueError("preferred_odds_ceiling must be <= max_odds_cap")

        # Validate API configuration
        # (Add API-specific validation as needed)

        # Validate logging configuration
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if config.logging.level not in valid_levels:
            raise ValueError(f"logging level must be one of {valid_levels}")

        return config

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        if self._config is None:
            self._load_config()
        return self._config

    def reload(self) -> None:
        """Reload configuration from files."""
        self._load_config()

    def get_betting_config(self) -> BettingConfig:
        """Get betting configuration."""
        return self.config.betting

    def get_api_config(self) -> APIConfig:
        """Get API configuration."""
        return self.config.api

    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        return self.config.logging


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def init_config(config_dir: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Initialize the global configuration manager with a specific config directory."""
    global _config_manager
    _config_manager = ConfigManager(config_dir)
    return _config_manager