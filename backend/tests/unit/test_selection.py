"""
Unit and property tests for Day-Ahead Forecast Selection Logic.
Verifies cut-off calculations, vintage ordering, selection invariants, error sign convention,
and missing forecast handling.
"""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.analytics.selection import (
    compute_decision_cutoff_utc,
    get_delivery_day_periods,
    select_day_ahead_forecast,
)
from app.db import build_engine, init_db
from app.ingest import load_seed_snapshot
from app.models import ActualWind, WindForecast


@pytest.fixture
def memory_db_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite session."""
    engine = build_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(engine)
    yield session
    session.close()


def test_cutoff_utc_derivation() -> None:
    """Test decision cut-off time conversion from London local time to UTC."""
    # January winter date (London is GMT / UTC+0)
    decision_d = date(2026, 1, 14)
    cutoff_utc = compute_decision_cutoff_utc(decision_d, "09:00", "Europe/London")

    assert cutoff_utc.year == 2026 and cutoff_utc.month == 1 and cutoff_utc.day == 14
    assert cutoff_utc.hour == 9 and cutoff_utc.minute == 0
    assert cutoff_utc.utcoffset() == UTC.utcoffset(None)

    # Summer date (London is BST / UTC+1) to ensure DST robustness
    summer_d = date(2026, 7, 10)
    cutoff_summer_utc = compute_decision_cutoff_utc(summer_d, "09:00", "Europe/London")
    assert cutoff_summer_utc.hour == 8  # 09:00 BST = 08:00 UTC


def test_delivery_day_period_generation() -> None:
    """Verify delivery day generates exactly 48 half-hour settlement periods."""
    delivery_d = date(2026, 1, 15)
    periods = get_delivery_day_periods(delivery_d, "Europe/London")

    assert len(periods) == 48

    first_target, first_sp = periods[0]
    last_target, last_sp = periods[47]

    assert first_sp == 1
    assert first_target.hour == 0 and first_target.minute == 0

    assert last_sp == 48
    assert last_target.hour == 23 and last_target.minute == 30


def test_latest_at_cutoff_selection_invariant(memory_db_session: Session) -> None:
    """
    Core Invariant Test:
    For target time T on day D, given multiple vintages published before and after cut-off C:
    1. Only vintages with publish_time <= C can be selected.
    2. Among all vintages <= C, the one with maximum publish_time must be chosen.
    3. Error sign convention: actual - forecast (negative = shortfall).
    """
    decision_d = date(2026, 1, 1)
    delivery_d = date(2026, 1, 2)
    target_utc = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)

    # Insert 3 vintages:
    # Vintage 1: Published at 06:00 on D-1 (eligible)
    # Vintage 2: Published at 08:45 on D-1 (eligible, latest before 09:00 cutoff) -> MUST BE SELECTED
    # Vintage 3: Published at 09:15 on D-1 (ineligible, after 09:00 cutoff)
    fc1 = WindForecast(
        start_time_utc=target_utc,
        publish_time_utc=datetime(2026, 1, 1, 6, 0, tzinfo=UTC),
        generation_mw=12000.0,
        horizon_hours=28.0,
    )
    fc2 = WindForecast(
        start_time_utc=target_utc,
        publish_time_utc=datetime(2026, 1, 1, 8, 45, tzinfo=UTC),
        generation_mw=14000.0,
        horizon_hours=25.25,
    )
    fc3 = WindForecast(
        start_time_utc=target_utc,
        publish_time_utc=datetime(2026, 1, 1, 9, 15, tzinfo=UTC),
        generation_mw=16000.0,
        horizon_hours=24.75,
    )
    # Insert actual: 11,000 MW (a shortfall of -3,000 MW against the 14,000 MW forecast)
    act = ActualWind(
        start_time_utc=target_utc,
        settlement_date="2026-01-02",
        settlement_period=21,
        generation_mw=11000.0,
        source_publish_time_utc=datetime(2026, 1, 2, 10, 30, tzinfo=UTC),
    )
    memory_db_session.add_all([fc1, fc2, fc3, act])
    memory_db_session.commit()

    # Run selection with cutoff 09:00
    res = select_day_ahead_forecast(memory_db_session, decision_d, cutoff_str="09:00")

    assert res.decision_date == decision_d.isoformat()
    assert res.delivery_date == delivery_d.isoformat()

    # Find the target point (period 21)
    target_point = next(p for p in res.points if p.start_time == target_utc)

    # Invariant checks
    assert target_point.forecast_mw == 14000.0, "Must select Vintage 2 (latest before 09:00 cutoff)"
    assert target_point.forecast_publish_time == datetime(2026, 1, 1, 8, 45, tzinfo=UTC)
    assert target_point.actual_mw == 11000.0
    assert target_point.error_mw == -3000.0, "Sign convention must be actual - forecast: negative = shortfall"
    assert target_point.horizon_hours == 25.25

    # Check cut-off shift: if cut-off is relaxed to 10:00, Vintage 3 must be selected
    res_relaxed = select_day_ahead_forecast(memory_db_session, decision_d, cutoff_str="10:00")
    point_relaxed = next(p for p in res_relaxed.points if p.start_time == target_utc)
    assert point_relaxed.forecast_mw == 16000.0
    assert point_relaxed.error_mw == -5000.0


def test_missing_forecast_reporting(memory_db_session: Session) -> None:
    """Verify missing forecasts are explicitly flagged and reported in coverage."""
    decision_d = date(2026, 1, 1)

    # Database has no forecasts inserted
    res = select_day_ahead_forecast(memory_db_session, decision_d, cutoff_str="09:00")

    assert res.coverage.periods == 48
    assert res.coverage.with_forecast == 0
    assert res.coverage.coverage_pct == 0.0

    for pt in res.points:
        assert pt.forecast_mw is None
        assert pt.error_mw is None
        assert pt.horizon_hours is None


def test_selection_against_real_seed(memory_db_session: Session) -> None:
    """Verify selection runs against real committed seed dataset for January 2026."""
    actuals, forecasts = load_seed_snapshot(memory_db_session)
    assert actuals > 0 and forecasts > 0

    # Test selection for decision date 2026-01-01 (delivery day 2026-01-02)
    res = select_day_ahead_forecast(memory_db_session, date(2026, 1, 1), cutoff_str="09:00")

    assert res.delivery_date == "2026-01-02"
    assert len(res.points) == 48
    assert res.coverage.with_actual == 48
    assert res.coverage.with_forecast > 0
    assert res.summary.actual_mwh is not None and res.summary.actual_mwh > 0
