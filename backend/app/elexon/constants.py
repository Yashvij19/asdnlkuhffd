"""
Constants, endpoint definitions, and query parameters for Elexon BMRS Insights API.
Verified against live API for January 2026 data.
"""

from typing import Final

# Elexon Stream Endpoints (relative to base URL https://data.elexon.co.uk/bmrs/api/v1)
ENDPOINT_FUELHH_STREAM: Final[str] = "/datasets/FUELHH/stream"
ENDPOINT_WINDFOR_STREAM: Final[str] = "/datasets/WINDFOR/stream"

# Dataset Identifiers
DATASET_FUELHH: Final[str] = "FUELHH"
DATASET_WINDFOR: Final[str] = "WINDFOR"
FUEL_TYPE_WIND: Final[str] = "WIND"

# Verified Query Parameters
# FUELHH/stream: settlementDateFrom (YYYY-MM-DD), settlementDateTo (YYYY-MM-DD), fuelType (e.g. WIND)
PARAM_FUELHH_DATE_FROM: Final[str] = "settlementDateFrom"
PARAM_FUELHH_DATE_TO: Final[str] = "settlementDateTo"
PARAM_FUELHH_FUEL_TYPE: Final[str] = "fuelType"

# WINDFOR/stream: publishDateTimeFrom (ISO8601 UTC), publishDateTimeTo (ISO8601 UTC)
PARAM_WINDFOR_PUBLISH_FROM: Final[str] = "publishDateTimeFrom"
PARAM_WINDFOR_PUBLISH_TO: Final[str] = "publishDateTimeTo"

# Schema Field Contracts
# Expected fields in FUELHH record
FUELHH_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "dataset",
    "publishTime",
    "startTime",
    "settlementDate",
    "settlementPeriod",
    "fuelType",
    "generation",
)

# Expected fields in WINDFOR record
WINDFOR_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "dataset",
    "publishTime",
    "startTime",
    "generation",
)

# Operational Defaults
DEFAULT_INGEST_CHUNK_DAYS: Final[int] = 3
ELEXON_USER_AGENT: Final[str] = "WindForecastMonitor/0.1.0"
