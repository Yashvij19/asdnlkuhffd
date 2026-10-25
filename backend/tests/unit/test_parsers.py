"""
Unit tests for Elexon BMRS row and batch parsers.
Covers valid parsing, horizon calculation, and defensive rejection of corrupt/invalid data.
"""

import json
from pathlib import Path

from app.elexon.parsers import (
    parse_fuelhh_batch,
    parse_fuelhh_row,
    parse_generation_mw,
    parse_iso_utc_timestamp,
    parse_windfor_batch,
    parse_windfor_row,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_parse_iso_utc_timestamp() -> None:
    """Verify ISO timestamp parsing converts strings to UTC-aware datetimes."""
    # Standard UTC format with Z
    dt = parse_iso_utc_timestamp("2026-01-02T14:30:00Z")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 1 and dt.day == 2
    assert dt.hour == 14 and dt.minute == 30
    offset = dt.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0

    # With offset
    dt2 = parse_iso_utc_timestamp("2026-01-02T15:30:00+01:00")
    assert dt2 is not None
    assert dt2.hour == 14 and dt2.minute == 30  # converted to UTC

    # Invalid values
    assert parse_iso_utc_timestamp("") is None
    assert parse_iso_utc_timestamp(None) is None
    assert parse_iso_utc_timestamp("not-a-date") is None


def test_parse_generation_mw() -> None:
    """Verify generation parser accepts finite non-negative values and rejects corrupt ones."""
    assert parse_generation_mw(15000) == 15000.0
    assert parse_generation_mw("14202.5") == 14202.5
    assert parse_generation_mw(0) == 0.0

    # Negative values
    assert parse_generation_mw(-1.0) is None
    assert parse_generation_mw("-500") is None

    # Non-finite values
    assert parse_generation_mw(float("nan")) is None
    assert parse_generation_mw(float("inf")) is None
    assert parse_generation_mw("nan") is None
    assert parse_generation_mw("inf") is None
    assert parse_generation_mw("abc") is None
    assert parse_generation_mw(None) is None


def test_fuelhh_fixture_batch_parsing() -> None:
    """Verify parse_fuelhh_batch successfully parses all 48 settlement periods from real fixture."""
    fixture_path = FIXTURES_DIR / "elexon_fuelhh_sample.json"
    with open(fixture_path, encoding="utf-8") as f:
        raw_rows = json.load(f)

    result = parse_fuelhh_batch(raw_rows)
    assert result.rejected_count == 0
    assert len(result.valid_rows) == 48

    first = result.valid_rows[0]
    assert first.settlement_date == "2026-01-02"
    assert first.generation_mw >= 0.0


def test_windfor_fixture_batch_parsing() -> None:
    """Verify parse_windfor_batch successfully parses real WINDFOR forecast fixture."""
    fixture_path = FIXTURES_DIR / "elexon_windfor_sample.json"
    with open(fixture_path, encoding="utf-8") as f:
        raw_rows = json.load(f)

    result = parse_windfor_batch(raw_rows)
    assert result.rejected_count == 0
    assert len(result.valid_rows) == len(raw_rows)

    # Check horizon calculation
    for row in result.valid_rows:
        expected_horizon = (row.start_time_utc - row.publish_time_utc).total_seconds() / 3600.0
        assert abs(row.horizon_hours - expected_horizon) < 1e-6


def test_defensive_fuelhh_rejections() -> None:
    """Verify FUELHH parser rejects invalid rows with descriptive rejection reasons."""
    valid_template = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-03T00:00:00Z",
        "startTime": "2026-01-02T23:30:00Z",
        "settlementDate": "2026-01-02",
        "settlementPeriod": 48,
        "fuelType": "WIND",
        "generation": 14202,
    }

    # 1. Negative generation
    bad_gen = {**valid_template, "generation": -100}
    record, err = parse_fuelhh_row(bad_gen)
    assert record is None and "generation value" in str(err)

    # 2. Non-wind fuel type
    bad_fuel = {**valid_template, "fuelType": "COAL"}
    record, err = parse_fuelhh_row(bad_fuel)
    assert record is None and "Expected fuelType 'WIND'" in str(err)

    # 3. Wrong dataset
    bad_ds = {**valid_template, "dataset": "OTHER"}
    record, err = parse_fuelhh_row(bad_ds)
    assert record is None and "Expected dataset 'FUELHH'" in str(err)

    # 4. Out of range settlement period
    bad_sp = {**valid_template, "settlementPeriod": 0}
    record, err = parse_fuelhh_row(bad_sp)
    assert record is None and "Invalid settlementPeriod" in str(err)

    # 5. Missing startTime
    bad_time = {**valid_template, "startTime": "invalid-time"}
    record, err = parse_fuelhh_row(bad_time)
    assert record is None and "Invalid or missing startTime" in str(err)


def test_defensive_windfor_rejections() -> None:
    """Verify WINDFOR parser rejects invalid rows with descriptive rejection reasons."""
    valid_template = {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T04:30:00Z",
        "startTime": "2026-01-01T20:00:00Z",
        "generation": 18500,
    }

    # 1. Negative generation
    bad_gen = {**valid_template, "generation": -5.0}
    record, err = parse_windfor_row(bad_gen)
    assert record is None and "generation value" in str(err)

    # 2. Corrupt generation string
    bad_str = {**valid_template, "generation": "corrupt"}
    record, err = parse_windfor_row(bad_str)
    assert record is None and "generation value" in str(err)

    # 3. Wrong dataset
    bad_ds = {**valid_template, "dataset": "WINDFOR_BAD"}
    record, err = parse_windfor_row(bad_ds)
    assert record is None and "Expected dataset 'WINDFOR'" in str(err)
