"""
Unit tests for Procurement Safety Buffer logic.
Verifies safety buffer calculation, confidence monotonicity, hourly profiles,
and risk-adjusted wind generation bounds.
"""

from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.analytics.buffer import calculate_procurement_buffer
from app.analytics.metrics import evaluate_period_accuracy
from app.db import build_engine, init_db
from app.ingest import load_seed_snapshot


@pytest.fixture
def memory_db_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite session with seed data."""
    engine = build_engine("sqlite:///:memory:")
    init_db(engine)
    session = Session(engine)
    load_seed_snapshot(session)
    yield session
    session.close()


def test_buffer_confidence_monotonicity(memory_db_session: Session) -> None:
    """
    Core Invariant Test:
    As confidence increases (e.g. 80% -> 90% -> 95%), the safety buffer
    MUST increase or stay equal: buffer(95%) >= buffer(90%) >= buffer(80%).
    """
    points, _, _ = evaluate_period_accuracy(
        memory_db_session,
        decision_from=date(2026, 1, 1),
        decision_to=date(2026, 1, 10),
        cutoff_str="09:00",
    )

    buf_80 = calculate_procurement_buffer(points, confidence=0.80)
    buf_90 = calculate_procurement_buffer(points, confidence=0.90)
    buf_95 = calculate_procurement_buffer(points, confidence=0.95)

    assert buf_80.overall_buffer_mw <= buf_90.overall_buffer_mw
    assert buf_90.overall_buffer_mw <= buf_95.overall_buffer_mw

    # All buffers must be non-negative
    assert buf_80.overall_buffer_mw >= 0.0
    assert buf_90.overall_buffer_mw >= 0.0
    assert buf_95.overall_buffer_mw >= 0.0

    # Risk adjusted wind <= mean forecast
    assert buf_90.overall_risk_adjusted_mw <= buf_90.overall_mean_forecast_mw


def test_hourly_buffer_profile(memory_db_session: Session) -> None:
    """Verify hourly buffers produce 24 hour buckets with valid bounds."""
    points, _, _ = evaluate_period_accuracy(
        memory_db_session,
        decision_from=date(2026, 1, 1),
        decision_to=date(2026, 1, 5),
        cutoff_str="09:00",
    )

    res = calculate_procurement_buffer(points, confidence=0.90)
    assert len(res.hourly_buffers) == 24

    for hb in res.hourly_buffers:
        assert 0 <= hb.hour <= 23
        assert hb.buffer_mw >= 0.0
        assert hb.risk_adjusted_wind_mw >= 0.0
        assert hb.risk_adjusted_wind_mw <= hb.mean_forecast_mw


def test_invalid_confidence_raises() -> None:
    """Verify confidence outside [0.50, 0.99] raises ValueError."""
    with pytest.raises(ValueError, match="Confidence must be between"):
        calculate_procurement_buffer([], confidence=0.40)

    with pytest.raises(ValueError, match="Confidence must be between"):
        calculate_procurement_buffer([], confidence=1.05)
