"""
Integration tests for Elexon client, ingestion pipeline, retries, circuit breaker,
idempotent upserts, and seed snapshot management.
"""

import json
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import build_engine, init_db
from app.elexon.client import CircuitBreaker, CircuitBreakerOpenError, ElexonClient
from app.elexon.constants import (
    ENDPOINT_FUELHH_STREAM,
    ENDPOINT_WINDFOR_STREAM,
)
from app.ingest import (
    create_seed_snapshot,
    ingest_fuelhh,
    ingest_windfor,
    load_seed_snapshot,
    upsert_actual_wind,
)
from app.models import ActualWind, WindForecast
from app.schemas import ActualWindCreate

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def test_db_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite session for integration tests."""
    engine = build_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(engine)
    yield session
    session.close()


@respx.mock
def test_fuelhh_ingestion_and_idempotence(test_db_session: Session) -> None:
    """
    Test end-to-end FUELHH ingestion against mocked Elexon API.
    Verifies audit logging in ingest_run and verifies idempotent upserts (FR-ING-6).
    """
    with open(FIXTURES_DIR / "elexon_fuelhh_sample.json", encoding="utf-8") as f:
        fixture_payload = json.load(f)

    # Mock the Elexon stream endpoint
    respx.get("https://data.elexon.co.uk/bmrs/api/v1" + ENDPOINT_FUELHH_STREAM).respond(
        status_code=200,
        json=fixture_payload,
    )

    client = ElexonClient()
    start_d = date(2026, 1, 2)
    end_d = date(2026, 1, 2)

    # 1. First Ingestion Run
    run1 = ingest_fuelhh(test_db_session, start_d, end_d, client=client)
    assert run1.status == "success"
    assert run1.rows_fetched == 48
    assert run1.rows_upserted == 48
    assert run1.rows_rejected == 0

    count1 = test_db_session.scalar(select(func.count()).select_from(ActualWind))
    assert count1 == 48

    # 2. Re-running Ingestion Must Be Idempotent (Never duplicate data)
    run2 = ingest_fuelhh(test_db_session, start_d, end_d, client=client)
    assert run2.status == "success"
    assert run2.rows_upserted == 48

    count2 = test_db_session.scalar(select(func.count()).select_from(ActualWind))
    assert count2 == 48, "Total rows must remain 48 without any duplicate records"


@respx.mock
def test_windfor_ingestion_success(test_db_session: Session) -> None:
    """Test end-to-end WINDFOR ingestion against mocked Elexon API."""
    with open(FIXTURES_DIR / "elexon_windfor_sample.json", encoding="utf-8") as f:
        fixture_payload = json.load(f)

    respx.get("https://data.elexon.co.uk/bmrs/api/v1" + ENDPOINT_WINDFOR_STREAM).respond(
        status_code=200,
        json=fixture_payload,
    )

    client = ElexonClient()
    start_dt = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    end_dt = datetime(2026, 1, 1, 6, 0, tzinfo=UTC)

    run = ingest_windfor(test_db_session, start_dt, end_dt, client=client)
    assert run.status == "success"
    assert run.rows_fetched == len(fixture_payload)
    assert run.rows_upserted == len(fixture_payload)

    count = test_db_session.scalar(select(func.count()).select_from(WindForecast))
    assert count == len(fixture_payload)


@respx.mock
def test_client_retries_on_429() -> None:
    """Verify ElexonClient automatically retries with backoff on HTTP 429 Too Many Requests."""
    route = respx.get("https://data.elexon.co.uk/bmrs/api/v1" + ENDPOINT_FUELHH_STREAM)
    # First attempt: 429 rate limit; Second attempt: 200 OK
    route.side_effect = [
        httpx.Response(status_code=429, json={"error": "Too Many Requests"}),
        httpx.Response(status_code=200, json=[{"dataset": "FUELHH", "fuelType": "WIND"}]),
    ]

    client = ElexonClient(max_retries=3)
    results = client._execute_request(ENDPOINT_FUELHH_STREAM, {"test": "val"})

    assert len(results) == 1
    assert route.call_count == 2, "Client must have retried after the 429 response"


@respx.mock
def test_circuit_breaker_trips_on_consecutive_failures() -> None:
    """Verify circuit breaker trips to OPEN after failure threshold and prevents further requests."""
    route = respx.get("https://data.elexon.co.uk/bmrs/api/v1" + ENDPOINT_FUELHH_STREAM)
    route.respond(status_code=500)

    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_s=60.0)
    client = ElexonClient(max_retries=1, circuit_breaker=breaker)

    # Call 1: fails
    with pytest.raises(httpx.HTTPStatusError):
        client._execute_request(ENDPOINT_FUELHH_STREAM, {})
    assert breaker.failure_count == 1
    assert breaker.state == "CLOSED"

    # Call 2: fails -> trips to OPEN
    with pytest.raises(httpx.HTTPStatusError):
        client._execute_request(ENDPOINT_FUELHH_STREAM, {})
    assert breaker.state == "OPEN"

    # Call 3: rejected immediately by circuit breaker without executing HTTP call
    with pytest.raises(CircuitBreakerOpenError):
        client._execute_request(ENDPOINT_FUELHH_STREAM, {})


def test_seed_snapshot_export_and_load(test_db_session: Session, tmp_path: Path) -> None:
    """Verify seed snapshot creation, checksum verification, and loading into an empty database."""
    # Seed one actual record in session
    now = datetime.now(UTC)
    record = ActualWindCreate(
        start_time_utc=now,
        settlement_date="2026-01-02",
        settlement_period=10,
        generation_mw=11000.0,
        source_publish_time_utc=now,
    )
    upsert_actual_wind(test_db_session, [record])

    # 1. Create Snapshot in tmp_path
    checksums = create_seed_snapshot(test_db_session, tmp_path)
    assert checksums["actuals_count"] == 1
    assert (tmp_path / "seed_actuals.json").exists()
    assert (tmp_path / "checksums.json").exists()

    # 2. In a brand new empty database, load the snapshot
    engine2 = build_engine("sqlite:///:memory:")
    init_db(engine2)
    session2 = Session(engine2)

    actuals_loaded, _ = load_seed_snapshot(session2, tmp_path)
    assert actuals_loaded == 1

    count = session2.scalar(select(func.count()).select_from(ActualWind))
    assert count == 1
    session2.close()
