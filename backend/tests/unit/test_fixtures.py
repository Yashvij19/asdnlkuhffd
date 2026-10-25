"""
Contract tests verifying the real Elexon BMRS API response fixtures.
Validates structure, types, field names, and value constraints for January 2026 data.
"""

import json
from datetime import datetime
from pathlib import Path

from app.elexon.constants import (
    DATASET_FUELHH,
    DATASET_WINDFOR,
    FUEL_TYPE_WIND,
    FUELHH_REQUIRED_FIELDS,
    WINDFOR_REQUIRED_FIELDS,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_fuelhh_fixture_contract() -> None:
    """Verify FUELHH fixture conforms to Elexon BMRS API schema and domain constraints."""
    fixture_path = FIXTURES_DIR / "elexon_fuelhh_sample.json"
    assert fixture_path.exists(), "FUELHH sample fixture file must exist"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "FUELHH response must be a list of records"
    assert len(data) == 48, "A complete delivery day must contain exactly 48 settlement periods"

    periods_seen = set()
    for row in data:
        # Field presence
        for field in FUELHH_REQUIRED_FIELDS:
            assert field in row, f"Missing required field '{field}' in FUELHH row: {row}"

        assert row["dataset"] == DATASET_FUELHH
        assert row["fuelType"] == FUEL_TYPE_WIND
        assert row["settlementDate"] == "2026-01-02"

        # Settlement period constraint (1 to 48)
        sp = row["settlementPeriod"]
        assert isinstance(sp, int) and 1 <= sp <= 48, f"Invalid settlement period {sp}"
        periods_seen.add(sp)

        # Generation constraints: finite, non-negative
        gen = row["generation"]
        assert isinstance(gen, (int, float)), f"Generation must be numeric, got {type(gen)}"
        assert gen >= 0, f"Wind generation cannot be negative, got {gen}"

        # Datetime ISO parsing
        start_dt = datetime.fromisoformat(row["startTime"].replace("Z", "+00:00"))
        pub_dt = datetime.fromisoformat(row["publishTime"].replace("Z", "+00:00"))
        assert start_dt.tzinfo is not None, "startTime must have timezone information"
        assert pub_dt.tzinfo is not None, "publishTime must have timezone information"

    assert len(periods_seen) == 48, "All 48 settlement periods must be present without duplicates"


def test_windfor_fixture_contract() -> None:
    """Verify WINDFOR fixture conforms to Elexon BMRS forecast schema and domain constraints."""
    fixture_path = FIXTURES_DIR / "elexon_windfor_sample.json"
    assert fixture_path.exists(), "WINDFOR sample fixture file must exist"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "WINDFOR response must be a list of records"
    assert len(data) > 0, "WINDFOR fixture must not be empty"

    for row in data:
        for field in WINDFOR_REQUIRED_FIELDS:
            assert field in row, f"Missing required field '{field}' in WINDFOR row: {row}"

        assert row["dataset"] == DATASET_WINDFOR

        # Generation numeric bounds
        gen = row["generation"]
        assert isinstance(gen, (int, float)), f"Forecast generation must be numeric, got {type(gen)}"
        assert gen >= 0, f"Forecast generation cannot be negative, got {gen}"

        # ISO Datetime format validation
        start_dt = datetime.fromisoformat(row["startTime"].replace("Z", "+00:00"))
        pub_dt = datetime.fromisoformat(row["publishTime"].replace("Z", "+00:00"))
        assert start_dt.tzinfo is not None
        assert pub_dt.tzinfo is not None
