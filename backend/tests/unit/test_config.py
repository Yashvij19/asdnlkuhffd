"""
Unit tests for application configuration and environment settings.
"""

from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_settings() -> None:
    """Verify default settings adhere strictly to the project specifications."""
    settings = Settings()

    assert settings.app_name == "Wind Generation Forecast Monitor"
    assert settings.app_version == "0.1.0"
    assert settings.decision_month_start == "2026-01-01"
    assert settings.decision_month_end == "2026-01-31"
    assert settings.default_cutoff == "09:00"
    assert settings.timezone == "Europe/London"
    assert settings.tz_info == ZoneInfo("Europe/London")
    assert settings.chunk_days == 3
    assert settings.http_timeout_s == 20
    assert settings.http_max_retries == 5
    assert "Elexon Limited copyright" in settings.attribution


def test_cutoff_validation() -> None:
    """Test cutoff validation ensures valid HH:MM 24-hour time."""
    # Valid cutoffs
    valid_cutoffs = ["00:00", "09:00", "12:30", "23:59"]
    for cutoff in valid_cutoffs:
        s = Settings(default_cutoff=cutoff)
        assert s.default_cutoff == cutoff

    # Invalid cutoffs
    invalid_cutoffs = ["9:00", "24:00", "12:60", "09:5", "random", ""]
    for cutoff in invalid_cutoffs:
        with pytest.raises(ValidationError):
            Settings(default_cutoff=cutoff)


def test_timezone_validation() -> None:
    """Test timezone validation accepts standard IANA timezones and rejects invalid ones."""
    s = Settings(timezone="UTC")
    assert s.timezone == "UTC"

    with pytest.raises(ValidationError):
        Settings(timezone="Invalid/Timezone_Name")


def test_cors_origins_parsing() -> None:
    """Test parsing comma-separated CORS origins into a clean string list."""
    # Empty
    s_empty = Settings(cors_origins="")
    assert s_empty.cors_origins_list == []

    # Single
    s_single = Settings(cors_origins="https://example.com")
    assert s_single.cors_origins_list == ["https://example.com"]

    # Multiple with whitespace
    s_multi = Settings(cors_origins="https://a.com, https://b.com , http://localhost:3000")
    assert s_multi.cors_origins_list == [
        "https://a.com",
        "https://b.com",
        "http://localhost:3000",
    ]
