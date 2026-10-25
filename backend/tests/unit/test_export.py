"""
Unit and Integration Tests for RFC 4180 Streaming CSV Export Engine (FR-API-4, Phase 3.3).
"""

import csv
import io
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.export import CSV_HEADERS, get_export_filename, stream_day_ahead_csv
from app.main import create_app
from app.models import ActualWind, WindForecast


def test_export_filename_format() -> None:
    """Verify attachment filename follows standard utility naming conventions."""
    fn = get_export_filename(date(2026, 1, 1), date(2026, 1, 31), "09:00")
    assert fn == "day_ahead_wind_forecast_20260101_20260131_cutoff_0900.csv"

    fn_single = get_export_filename(date(2026, 1, 15), date(2026, 1, 15), "12:00")
    assert fn_single == "day_ahead_wind_forecast_20260115_20260115_cutoff_1200.csv"


def test_rfc4180_csv_format_and_crlf_line_endings(memory_db_session: Session) -> None:
    """Verify streaming generator strictly adheres to RFC 4180 with CRLF terminators."""
    # Delivery day: 2026-01-05 (Decision day: 2026-01-04)
    dec_date = date(2026, 1, 4)

    t1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 5, 12, 30, tzinfo=UTC)

    # Add actuals
    memory_db_session.add(
        ActualWind(
            start_time_utc=t1,
            settlement_date="2026-01-05",
            settlement_period=25,
            generation_mw=12000.0,
            source_publish_time_utc=t1,
        )
    )
    memory_db_session.add(
        ActualWind(
            start_time_utc=t2,
            settlement_date="2026-01-05",
            settlement_period=26,
            generation_mw=12500.0,
            source_publish_time_utc=t2,
        )
    )

    # Add forecast published at D-1 08:30 (before 09:00 cut-off)
    pub_time = datetime(2026, 1, 4, 8, 30, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(
            start_time_utc=t1,
            publish_time_utc=pub_time,
            generation_mw=11000.0,
            horizon_hours=27.5,
        )
    )
    memory_db_session.add(
        WindForecast(
            start_time_utc=t2,
            publish_time_utc=pub_time,
            generation_mw=13000.0,
            horizon_hours=28.0,
        )
    )
    memory_db_session.commit()

    # Stream CSV chunks
    chunks = list(
        stream_day_ahead_csv(
            session=memory_db_session,
            decision_from=dec_date,
            decision_to=dec_date,
            cutoff_str="09:00",
        )
    )

    full_csv = "".join(chunks)

    # 1. Check RFC 4180 CRLF line ending invariant
    assert "\r\n" in full_csv
    lines = full_csv.split("\r\n")
    # Last item after trailing \r\n should be empty string
    assert lines[-1] == ""
    assert len(lines) == 50  # 1 header + 48 settlement periods + 1 trailing empty

    # 2. Parse with Python standard csv.reader
    reader = csv.reader(io.StringIO(full_csv))
    rows = list(reader)
    assert len(rows) == 49  # 1 header + 48 rows

    # 3. Check header columns
    assert rows[0] == CSV_HEADERS

    # 4. Check data in rows
    # Period 25: actual=12000, fc=11000 -> error = +1000 -> SURPLUS
    p25_row = next(r for r in rows[1:] if r[1] == "25")
    assert p25_row[0] == "2026-01-05"
    assert p25_row[8] == "11000.0"
    assert p25_row[9] == "12000.0"
    assert p25_row[10] == "1000.0"
    assert p25_row[11] == "1000.0"
    assert p25_row[12] == "SURPLUS"

    # Period 26: actual=12500, fc=13000 -> error = -500 -> SHORTFALL
    p26_row = next(r for r in rows[1:] if r[1] == "26")
    assert p26_row[8] == "13000.0"
    assert p26_row[9] == "12500.0"
    assert p26_row[10] == "-500.0"
    assert p26_row[11] == "500.0"
    assert p26_row[12] == "SHORTFALL"


def test_export_endpoint_integration() -> None:
    """Test HTTP streaming response headers and content via FastAPI TestClient."""
    app = create_app()
    with TestClient(app) as client:
        # 1. Single delivery date export
        resp = client.get("/api/v1/export/day-ahead.csv?delivery_date=2026-01-15&cutoff=09:00")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        assert "day_ahead_wind_forecast_20260114_20260114_cutoff_0900.csv" in resp.headers["content-disposition"]

        content = resp.text
        assert "\r\n" in content
        rows = list(csv.reader(io.StringIO(content)))
        assert rows[0] == CSV_HEADERS
        assert len(rows) == 49  # 1 header + 48 settlement periods

        # 2. Date range export across 3 days
        resp_range = client.get(
            "/api/v1/export/day-ahead.csv?from=2026-01-01&to=2026-01-03&cutoff=09:00"
        )
        assert resp_range.status_code == 200
        rows_range = list(csv.reader(io.StringIO(resp_range.text)))
        assert len(rows_range) == 1 + (3 * 48)  # 1 header + 144 periods

        # 3. Validation errors
        bad_resp = client.get("/api/v1/export/day-ahead.csv?from=2026-01-05&to=2026-01-02")
        assert bad_resp.status_code == 400

        bad_date = client.get("/api/v1/export/day-ahead.csv?delivery_date=invalid-date")
        assert bad_date.status_code == 400
