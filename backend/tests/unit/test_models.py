"""
Unit tests for SQLAlchemy models, table bootstrap, and constraints.
"""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import build_engine, init_db
from app.models import ActualWind, IngestRun, WindForecast


@pytest.fixture
def memory_db_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite database session for testing."""
    engine = build_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(engine)
    yield session
    session.close()


def test_actual_wind_crud_and_constraints(memory_db_session: Session) -> None:
    """Verify ActualWind model persistence, querying, and unique primary key enforcement."""
    dt = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    pub = datetime(2026, 1, 2, 12, 30, tzinfo=UTC)

    actual = ActualWind(
        start_time_utc=dt,
        settlement_date="2026-01-02",
        settlement_period=25,
        generation_mw=12500.5,
        source_publish_time_utc=pub,
    )
    memory_db_session.add(actual)
    memory_db_session.commit()

    # Query back
    stmt = select(ActualWind).where(ActualWind.settlement_date == "2026-01-02")
    results = memory_db_session.scalars(stmt).all()
    assert len(results) == 1
    assert results[0].generation_mw == 12500.5
    assert results[0].settlement_period == 25

    # Test Primary Key collision on start_time_utc
    duplicate = ActualWind(
        start_time_utc=dt,
        settlement_date="2026-01-02",
        settlement_period=25,
        generation_mw=9999.0,
        source_publish_time_utc=pub,
    )
    memory_db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        memory_db_session.commit()
    memory_db_session.rollback()


def test_wind_forecast_composite_key(memory_db_session: Session) -> None:
    """Verify WindForecast composite primary key (start_time_utc, publish_time_utc)."""
    target_time = datetime(2026, 1, 3, 14, 0, tzinfo=UTC)
    pub1 = datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
    pub2 = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)

    # Two distinct vintages for the same target time are allowed
    fc1 = WindForecast(
        start_time_utc=target_time,
        publish_time_utc=pub1,
        generation_mw=15000.0,
        horizon_hours=30.0,
    )
    fc2 = WindForecast(
        start_time_utc=target_time,
        publish_time_utc=pub2,
        generation_mw=15200.0,
        horizon_hours=29.0,
    )
    memory_db_session.add_all([fc1, fc2])
    memory_db_session.commit()

    # Query vintages ordered by publish_time desc
    stmt = select(WindForecast).where(
        WindForecast.start_time_utc == target_time
    ).order_by(WindForecast.publish_time_utc.desc())
    vintages = memory_db_session.scalars(stmt).all()
    assert len(vintages) == 2
    assert vintages[0].generation_mw == 15200.0
    assert vintages[1].generation_mw == 15000.0

    # Duplicate vintage (same target and same publish time) must fail
    dup = WindForecast(
        start_time_utc=target_time,
        publish_time_utc=pub2,
        generation_mw=16000.0,
        horizon_hours=29.0,
    )
    memory_db_session.add(dup)
    with pytest.raises(IntegrityError):
        memory_db_session.commit()
    memory_db_session.rollback()


def test_ingest_run_lifecycle(memory_db_session: Session) -> None:
    """Verify IngestRun creation, status updating, and row counting."""
    now = datetime.now(UTC)
    run = IngestRun(
        started_at=now,
        status="running",
        dataset="FUELHH",
        range_from="2026-01-02",
        range_to="2026-01-04",
        rows_fetched=144,
        rows_upserted=0,
        rows_rejected=0,
    )
    memory_db_session.add(run)
    memory_db_session.commit()
    assert run.id is not None

    # Update completion
    run.status = "success"
    run.rows_upserted = 144
    run.finished_at = datetime.now(UTC)
    memory_db_session.commit()

    saved_run = memory_db_session.get(IngestRun, run.id)
    assert saved_run is not None
    assert saved_run.status == "success"
    assert saved_run.rows_upserted == 144
