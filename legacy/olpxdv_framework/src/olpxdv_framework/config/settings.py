"""
Configuration management using Pydantic Settings.

This module provides type-safe configuration with validation,
environment variable support, and automatic documentation generation.
"""

from __future__ import annotations
from typing import List, Optional
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from decimal import Decimal


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    url: str = Field(default="sqlite+aiosqlite:///./data/olpxdv.db", description="Database connection URL")
    echo: bool = Field(default=False, description="Echo SQL statements")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")

    model_config = SettingsConfigDict(env_prefix="DB_")


class APISettings(BaseSettings):
    """External API configuration"""

    # The Odds API
    odds_api_key: str = Field(default="", description="The Odds API key")
    odds_api_base_url: str = Field(default="https://api.the-odds-api.com/v4", description="The Odds API base URL")
    odds_api_timeout: int = Field(default=30, description="Request timeout in seconds")
    odds_api_rate_limit: int = Field(default=60, description="Max requests per minute")

    # API-Football
    api_football_key: str = Field(default="", description="API-Football key")
    api_football_base_url: str = Field(default="https://v3.football.api-sports.io", description="API-Football base URL")
    api_football_timeout: int = Field(default=30, description="Request timeout in seconds")
    api_football_rate_limit: int = Field(default=100, description="Max requests per minute")

    # TheSportsDB
    sportsdb_base_url: str = Field(default="https://www.thesportsdb.com/api/v1/json/1", description="TheSportsDB base URL")
    sportsdb_timeout: int = Field(default=30, description="Request timeout in seconds")

    # Telegram Bot
    telegram_bot_token: str = Field(default="", description="Telegram Bot API token")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID for notifications")
    telegram_board_delivery_enabled: bool = Field(default=False, description="Enable daily Telegram board delivery")

    # MCP Server API Keys
    perplexity_api_key: str = Field(default="", description="Perplexity API key for MCP server")
    firecrawl_api_key: str = Field(default="", description="Firecrawl API key for MCP server")

    model_config = SettingsConfigDict(env_prefix="API_")


class SecuritySettings(BaseSettings):
    """Security and authentication configuration"""
    secret_key: str = Field(default="change-me-in-production", description="Secret key for JWT tokens")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiry in minutes")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token expiry in days")

    # Admin dashboard
    admin_username: str = Field(default="architect", description="Admin dashboard username")
    admin_password_hash: str = Field(default="", description="Admin password hash (bcrypt)")

    model_config = SettingsConfigDict(env_prefix="SEC_")


class FrameworkSettings(BaseSettings):
    """Core framework configuration"""

    # Phase configuration
    current_phase: int = Field(default=3, ge=1, le=3, description="Current framework phase")
    paper_only_below_phase: int = Field(default=3, ge=1, le=3, description="Phase below which only paper trading")

    # CLV Gate
    clv_min_legs: int = Field(default=30, ge=10, le=100, description="Minimum legs for CLV gate")
    clv_mean_threshold: Decimal = Field(default=Decimal('0.0'), description="Mean CLV threshold (percentage)")
    clv_window_hours: int = Field(default=24, ge=1, le=168, description="Hours before kickoff for closing lines")

    # Capital Deployment
    max_kelly_fraction: Decimal = Field(default=Decimal('0.25'), ge=0, le=1, description="Max Kelly fraction")
    max_daily_exposure: Decimal = Field(default=Decimal('1000.0'), ge=0, description="Max daily exposure (units)")
    max_single_bet_exposure: Decimal = Field(default=Decimal('100.0'), ge=0, description="Max single bet exposure (units)")

    # Client Publishing
    client_publish_enabled: bool = Field(default=False, description="Enable client publishing")
    min_edge_for_publish: Decimal = Field(default=Decimal('0.03'), ge=0, le=1, description="Min edge for publishing")

    # Model Reuse
    model_reuse_days: int = Field(default=7, ge=1, le=30, description="Days before model reuse")

    # Schema Validation
    strict_schema_mode: bool = Field(default=True, description="Strict schema validation")

    # Fixture Eligibility
    all_fixtures_eligible: bool = Field(default=True, description="All fixtures eligible regardless of tier")

    # ID405 Override
    id405_allow_away_wins: bool = Field(default=True, description="Allow away win recommendations")

    # Booking
    booking_code_expiry_minutes: int = Field(default=60, ge=5, le=1440, description="Booking code expiry")
    sportybet_max_odds: Decimal = Field(default=Decimal('50.0'), ge=1, description="Max odds SportyBet accepts")
    sportybet_bridge_timeout: int = Field(default=30, ge=1, le=300, description="SportyBet bridge timeout in seconds")

    # Fabrication Detection
    fabrication_detection_enabled: bool = Field(default=True, description="Enable fabrication detection")
    fabrication_threshold: Decimal = Field(default=Decimal('0.95'), ge=0.5, le=1, description="Fabrication confidence threshold")

    # Knowledge Persistence
    knowledge_relevance_half_life_days: int = Field(default=30, ge=1, le=365, description="Knowledge relevance half-life")
    vault_memory_sync_interval_minutes: int = Field(default=30, ge=5, le=1440, description="Vault-memory sync interval")

    # Risk Management
    max_drawdown_percentage: Decimal = Field(default=Decimal('20.0'), ge=0, le=100, description="Max drawdown %")
    min_sample_size_for_clv: int = Field(default=50, ge=30, le=1000, description="Min sample size for CLV")

    # League Whitelist
    whitelisted_leagues: List[str] = Field(default=[
        "Premier League",
        "Championship",
        "Bundesliga",
        "Serie A",
        "Ligue 1",
        "La Liga",
        "Primeira Liga",
        "Eredivisie",
        "Scottish Premiership",
        "Belgian Pro League",
        "Turkish Super Lig",
        "Swiss Super League",
        "Russian Premier League",
        "Serie B",
        "La Liga 2",
        "Ligue 2"
    ], description="Whitelisted leagues for scanning")

    # Default MES floor
    min_mes_floor: Decimal = Field(default=Decimal('0.03'), ge=0, le=1, description="Minimum MES floor")

    model_config = SettingsConfigDict(env_prefix="FRAMEWORK_")


class ObservabilitySettings(BaseSettings):
    """Observability and monitoring configuration"""

    # Logging
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    log_format: str = Field(default="json", description="Log format (json, text)")
    log_file: str = Field(default="logs/olpxdv.log", description="Log file path")

    # Metrics
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, description="Prometheus metrics port")
    metrics_path: str = Field(default="/metrics", description="Prometheus metrics endpoint path")

    # Health checks
    health_check_interval: int = Field(default=60, description="Health check interval in seconds")

    model_config = SettingsConfigDict(env_prefix="OBS_")


class DesktopSettings(BaseSettings):
    """Desktop application specific settings"""
    auto_start: bool = Field(default=False, description="Auto-start on system boot")
    system_tray: bool = Field(default=True, description="Show system tray icon")
    notifications: bool = Field(default=True, description="Enable desktop notifications")
    window_width: int = Field(default=1200, description="Default window width")
    window_height: int = Field(default=800, description="Default window height")

    model_config = SettingsConfigDict(env_prefix="DESKTOP_")


class Settings(BaseSettings):
    """Main settings aggregator"""
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    framework: FrameworkSettings = Field(default_factory=FrameworkSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    desktop: DesktopSettings = Field(default_factory=DesktopSettings)

    # Application info
    app_name: str = Field(default="OLP XDV Framework", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="allow"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded once and reused.
    """
    return Settings()


def reload_settings() -> Settings:
    """Force reload of settings (clears cache)"""
    get_settings.cache_clear()
    return get_settings()


# Convenience accessor functions
def get_database_url() -> str:
    return get_settings().database.url


def get_api_odds_key() -> str:
    return get_settings().api.odds_api_key


def get_api_football_key() -> str:
    return get_settings().api.api_football_key


def get_telegram_bot_token() -> str:
    return get_settings().api.telegram_bot_token


def get_telegram_chat_id() -> str:
    return get_settings().api.telegram_chat_id


def get_secret_key() -> str:
    return get_settings().security.secret_key


def get_current_phase() -> int:
    return get_settings().framework.current_phase


def get_clv_min_legs() -> int:
    return get_settings().framework.clv_min_legs


def get_clv_mean_threshold() -> Decimal:
    return get_settings().framework.clv_mean_threshold


def get_max_kelly_fraction() -> Decimal:
    return get_settings().framework.max_kelly_fraction


def get_client_publish_enabled() -> bool:
    return get_settings().framework.client_publish_enabled


def get_whitelisted_leagues() -> List[str]:
    return get_settings().framework.whitelisted_leagues


def get_min_mes_floor() -> Decimal:
    return get_settings().framework.min_mes_floor


def is_debug_mode() -> bool:
    return get_settings().debug