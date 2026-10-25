"""
Configuration management for the Wind Generation Forecast Monitor.
Loads settings from environment variables with strong typing, validation, and defaults.
"""

import re
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application
    app_name: str = "Wind Generation Forecast Monitor"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", description="development | production | test")
    port: int = Field(default=8000, description="Server port")
    log_level: str = Field(default="INFO", description="DEBUG | INFO | WARNING | ERROR")

    # Storage
    database_url: str = Field(
        default="sqlite:///./data/app.db",
        description="SQLAlchemy database connection string",
    )

    # External Data Source (Elexon BMRS)
    elexon_base_url: str = Field(
        default="https://data.elexon.co.uk/bmrs/api/v1",
        description="Elexon Insights API base URL",
    )
    chunk_days: int = Field(
        default=3,
        ge=1,
        le=31,
        description="Ingestion date chunk window in days",
    )
    http_timeout_s: int = Field(
        default=20,
        ge=1,
        le=120,
        description="HTTP client timeout in seconds",
    )
    http_max_retries: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Max retries for transient HTTP errors",
    )

    # Domain & Market Rules
    decision_month_start: str = Field(
        default="2026-01-01",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date of decision month (YYYY-MM-DD)",
    )
    decision_month_end: str = Field(
        default="2026-01-31",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date of decision month (YYYY-MM-DD)",
    )
    default_cutoff: str = Field(
        default="09:00",
        description="Default decision cut-off time on D-1 (HH:MM in London time)",
    )
    timezone: str = Field(
        default="Europe/London",
        description="Market timezone",
    )

    # Security & API Protection
    admin_api_key: str | None = Field(
        default=None,
        description="Secret key required for protected /admin endpoints",
    )
    cors_origins: str = Field(
        default="",
        description="Comma-separated list of allowed CORS origins",
    )
    rate_limit: str = Field(
        default="120/minute",
        description="Slowapi rate limit string",
    )

    # Attribution
    attribution: str = (
        "Contains BMRS data © Elexon Limited copyright and database right"
    )

    @field_validator("default_cutoff")
    @classmethod
    def validate_cutoff(cls, v: str) -> str:
        """Ensure cut-off is formatted as valid 24-hour HH:MM."""
        if not re.match(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$", v):
            raise ValueError("default_cutoff must be formatted as HH:MM (24-hour format, 00:00 - 23:59)")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string against standard IANA database."""
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as err:
            raise ValueError(
                f"Unknown timezone '{v}'. Must be a valid IANA timezone identifier."
            ) from err
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Return parsed list of CORS origin strings."""
        if not self.cors_origins.strip():
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def tz_info(self) -> ZoneInfo:
        """Return the ZoneInfo instance for the configured timezone."""
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()
