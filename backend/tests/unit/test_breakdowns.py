"""
Unit tests for Breakdowns Analytics.
Verifies multi-dimensional slicing by delivery day, hour of day, forecast lead horizon,
power generation tier, and weekday vs weekend.
"""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.analytics.breakdowns import (
    compute_breakdown_by_day,
    compute_breakdown_by_horizon,
    compute_breakdown_by_hour,
    compute_breakdown_by_level,
    compute_breakdown_by_weekday,
)
from app.analytics.metrics import evaluate_period_accuracy
from app.db import build_engine, init_db
from app.ingest import load_seed_snapshot
from app.schemas import DayAheadPoint


@pytest.fixture
def memory_db_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite session with seed data."""
    engine = build_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(engine)
    load_seed_snapshot(session)
    yield session
    session.close()


def test_breakdown_by_hour_completeness(memory_db_session: Session) -> None:
    """Verify breakdown by hour produces exactly 24 hours (0..23) and conserves sample count."""
    points, _, _ = evaluate_period_accuracy(
        memory_db_session,
        decision_from=date(2026, 1, 1),
        decision_to=date(2026, 1, 7),
        cutoff_str="09:00",
    )

    hourly = compute_breakdown_by_hour(points)
    assert len(hourly) == 24

    for i, h in enumerate(hourly):
        assert h.dimension_key == f"{i:02d}"
        assert f"{i:02d}:00" in h.dimension_label
        assert h.count >= 0

    valid_points_count = len([p for p in points if p.error_mw is not None])
    total_hourly_count = sum(h.count for h in hourly)
    assert total_hourly_count == valid_points_count


def test_breakdown_by_day(memory_db_session: Session) -> None:
    """Verify breakdown by delivery day covers each day in order."""
    points, _, days_count = evaluate_period_accuracy(
        memory_db_session,
        decision_from=date(2026, 1, 1),
        decision_to=date(2026, 1, 5),
        cutoff_str="09:00",
    )

    daily = compute_breakdown_by_day(points)
    assert len(daily) == days_count

    # Check date progression
    expected_days = ["2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06"]
    for item, expected_day in zip(daily, expected_days, strict=True):
        assert item.dimension_key == expected_day
        assert item.count > 0
        assert item.mae_mw >= 0


def test_breakdown_by_horizon() -> None:
    """Verify points fall into correct lead time horizon buckets."""
    now = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    points = [
        DayAheadPoint(start_time=now, settlement_period=1, forecast_mw=100.0, actual_mw=90.0, error_mw=-10.0, horizon_hours=15.0),
        DayAheadPoint(start_time=now, settlement_period=2, forecast_mw=100.0, actual_mw=90.0, error_mw=-10.0, horizon_hours=20.0),
        DayAheadPoint(start_time=now, settlement_period=3, forecast_mw=100.0, actual_mw=90.0, error_mw=-10.0, horizon_hours=26.0),
        DayAheadPoint(start_time=now, settlement_period=4, forecast_mw=100.0, actual_mw=90.0, error_mw=-10.0, horizon_hours=32.0),
        DayAheadPoint(start_time=now, settlement_period=5, forecast_mw=100.0, actual_mw=90.0, error_mw=-10.0, horizon_hours=40.0),
        DayAheadPoint(start_time=now, settlement_period=6, forecast_mw=100.0, actual_mw=90.0, error_mw=-10.0, horizon_hours=45.0),
    ]

    horizon_items = compute_breakdown_by_horizon(points)
    assert len(horizon_items) == 6
    # Each bucket should have exactly 1 item
    for item in horizon_items:
        assert item.count == 1
        assert item.bias_mw == -10.0


def test_breakdown_by_wind_level() -> None:
    """Verify power tier classification."""
    now = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    points = [
        DayAheadPoint(start_time=now, settlement_period=1, forecast_mw=2500.0, actual_mw=2000.0, error_mw=-500.0),
        DayAheadPoint(start_time=now, settlement_period=2, forecast_mw=7500.0, actual_mw=7000.0, error_mw=-500.0),
        DayAheadPoint(start_time=now, settlement_period=3, forecast_mw=12000.0, actual_mw=11000.0, error_mw=-1000.0),
        DayAheadPoint(start_time=now, settlement_period=4, forecast_mw=18000.0, actual_mw=17000.0, error_mw=-1000.0),
    ]

    tier_items = compute_breakdown_by_level(points)
    assert len(tier_items) == 4
    for item in tier_items:
        assert item.count == 1


def test_breakdown_by_weekday() -> None:
    """Verify classification into weekday vs weekend."""
    # 2026-01-02 was Friday (weekday), 2026-01-03 was Saturday (weekend)
    fri = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    sat = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)

    points = [
        DayAheadPoint(start_time=fri, settlement_period=25, forecast_mw=1000.0, actual_mw=900.0, error_mw=-100.0),
        DayAheadPoint(start_time=sat, settlement_period=25, forecast_mw=2000.0, actual_mw=1800.0, error_mw=-200.0),
    ]

    weekday_items = compute_breakdown_by_weekday(points)
    assert len(weekday_items) == 2
    assert weekday_items[0].dimension_key == "weekday"
    assert weekday_items[0].count == 1
    assert weekday_items[1].dimension_key == "weekend"
    assert weekday_items[1].count == 1
