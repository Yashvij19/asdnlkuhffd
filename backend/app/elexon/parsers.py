"""
Defensive row normalisation and validation parsers for Elexon BMRS API payloads.
Converts raw dictionary responses into validated Pydantic models.
"""

import math
from datetime import UTC, datetime
from typing import Any

from app.elexon.constants import (
    DATASET_FUELHH,
    DATASET_WINDFOR,
    FUEL_TYPE_WIND,
)
from app.logging import get_logger
from app.schemas import ActualWindCreate, ParsedBatch, WindForecastCreate

logger = get_logger("app.elexon.parsers")


def parse_iso_utc_timestamp(val: Any) -> datetime | None:
    """Safely parse an ISO-8601 string or datetime into a UTC-aware datetime object."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val.astimezone(UTC)

    if not isinstance(val, str) or not val.strip():
        return None

    try:
        clean_str = val.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def parse_generation_mw(val: Any) -> float | None:
    """Validate that generation value is a finite, non-negative floating-point number."""
    if val is None:
        return None

    try:
        num = float(val)
        if math.isnan(num) or math.isinf(num):
            return None
        if num < 0.0:
            return None
        return num
    except (ValueError, TypeError):
        return None


def parse_fuelhh_row(raw: dict[str, Any]) -> tuple[ActualWindCreate | None, str | None]:
    """
    Parse a single FUELHH wind generation dictionary into ActualWindCreate.
    Returns (model, None) on success, or (None, rejection_reason) on validation failure.
    """
    if not isinstance(raw, dict):
        return None, "Row is not a dictionary"

    # Dataset & fuelType checks
    dataset = raw.get("dataset")
    if dataset != DATASET_FUELHH:
        return None, f"Expected dataset '{DATASET_FUELHH}', got '{dataset}'"

    fuel_type = raw.get("fuelType")
    if fuel_type != FUEL_TYPE_WIND:
        return None, f"Expected fuelType '{FUEL_TYPE_WIND}', got '{fuel_type}'"

    # Timestamps
    start_time = parse_iso_utc_timestamp(raw.get("startTime"))
    if not start_time:
        return None, f"Invalid or missing startTime: {raw.get('startTime')}"

    publish_time = parse_iso_utc_timestamp(raw.get("publishTime"))
    if not publish_time:
        return None, f"Invalid or missing publishTime: {raw.get('publishTime')}"

    # Settlement date & period
    settlement_date = raw.get("settlementDate")
    if not isinstance(settlement_date, str) or not settlement_date.strip():
        return None, f"Invalid or missing settlementDate: {settlement_date}"

    settlement_period = raw.get("settlementPeriod")
    if not isinstance(settlement_period, int) or settlement_period < 1 or settlement_period > 50:
        return None, f"Invalid settlementPeriod: {settlement_period} (must be integer 1-50)"

    # Generation
    gen_mw = parse_generation_mw(raw.get("generation"))
    if gen_mw is None:
        return None, f"Invalid generation value: {raw.get('generation')} (must be finite number >= 0)"

    try:
        record = ActualWindCreate(
            start_time_utc=start_time,
            settlement_date=settlement_date.strip(),
            settlement_period=settlement_period,
            generation_mw=gen_mw,
            source_publish_time_utc=publish_time,
        )
        return record, None
    except Exception as err:
        return None, f"Pydantic validation error: {err}"


def parse_windfor_row(raw: dict[str, Any]) -> tuple[WindForecastCreate | None, str | None]:
    """
    Parse a single WINDFOR forecast dictionary into WindForecastCreate.
    Returns (model, None) on success, or (None, rejection_reason) on validation failure.
    """
    if not isinstance(raw, dict):
        return None, "Row is not a dictionary"

    dataset = raw.get("dataset")
    if dataset != DATASET_WINDFOR:
        return None, f"Expected dataset '{DATASET_WINDFOR}', got '{dataset}'"

    start_time = parse_iso_utc_timestamp(raw.get("startTime"))
    if not start_time:
        return None, f"Invalid or missing startTime: {raw.get('startTime')}"

    publish_time = parse_iso_utc_timestamp(raw.get("publishTime"))
    if not publish_time:
        return None, f"Invalid or missing publishTime: {raw.get('publishTime')}"

    gen_mw = parse_generation_mw(raw.get("generation"))
    if gen_mw is None:
        return None, f"Invalid generation value: {raw.get('generation')} (must be finite number >= 0)"

    # Lead time horizon in hours: (start_time - publish_time)
    horizon_hours = (start_time - publish_time).total_seconds() / 3600.0

    try:
        record = WindForecastCreate(
            start_time_utc=start_time,
            publish_time_utc=publish_time,
            generation_mw=gen_mw,
            horizon_hours=horizon_hours,
        )
        return record, None
    except Exception as err:
        return None, f"Pydantic validation error: {err}"


def parse_fuelhh_batch(rows: list[dict[str, Any]]) -> ParsedBatch[ActualWindCreate]:
    """Parse and validate an entire batch of FUELHH records, separating valid items from rejects."""
    valid_records: list[ActualWindCreate] = []
    rejections: list[str] = []

    for idx, raw in enumerate(rows):
        record, error = parse_fuelhh_row(raw)
        if record:
            valid_records.append(record)
        else:
            rejections.append(f"Row {idx}: {error}")

    if rejections:
        logger.warning(
            "fuelhh_batch_had_rejections",
            total=len(rows),
            valid=len(valid_records),
            rejected=len(rejections),
            sample_rejections=rejections[:5],
        )

    return ParsedBatch[ActualWindCreate](
        valid_rows=valid_records,
        rejected_count=len(rejections),
        rejections=rejections,
    )


def parse_windfor_batch(rows: list[dict[str, Any]]) -> ParsedBatch[WindForecastCreate]:
    """Parse and validate an entire batch of WINDFOR records, separating valid items from rejects."""
    valid_records: list[WindForecastCreate] = []
    rejections: list[str] = []

    for idx, raw in enumerate(rows):
        record, error = parse_windfor_row(raw)
        if record:
            valid_records.append(record)
        else:
            rejections.append(f"Row {idx}: {error}")

    if rejections:
        logger.warning(
            "windfor_batch_had_rejections",
            total=len(rows),
            valid=len(valid_records),
            rejected=len(rejections),
            sample_rejections=rejections[:5],
        )

    return ParsedBatch[WindForecastCreate](
        valid_rows=valid_records,
        rejected_count=len(rejections),
        rejections=rejections,
    )
