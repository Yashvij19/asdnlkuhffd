"""
Unit tests for Headline Accuracy Metrics & Error Distribution.
Verifies exact hand-computed values, mathematical identities (RMSE >= MAE),
quantile monotonicity, histogram bin integrity, and full seed data evaluation.
"""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.analytics.metrics import (
    calculate_accuracy_metrics,
    calculate_error_distribution,
    compute_quantiles,
    get_accuracy_summary,
    get_error_distribution,
)
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


def test_hand_computed_accuracy_metrics() -> None:
    """
    Verify metrics against an exact hand-computed dataset of 5 periods:
    Point 1: actual=100, forecast=120 -> error = -20 (shortfall)
    Point 2: actual=200, forecast=180 -> error = +20 (surplus)
    Point 3: actual=150, forecast=150 -> error =   0 (balanced)
    Point 4: actual=300, forecast=350 -> error = -50 (shortfall)
    Point 5: actual=250, forecast=200 -> error = +50 (surplus)
    """
    now = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    points = [
        DayAheadPoint(start_time=now, settlement_period=1, forecast_mw=120.0, actual_mw=100.0, error_mw=-20.0),
        DayAheadPoint(start_time=now, settlement_period=2, forecast_mw=180.0, actual_mw=200.0, error_mw=20.0),
        DayAheadPoint(start_time=now, settlement_period=3, forecast_mw=150.0, actual_mw=150.0, error_mw=0.0),
        DayAheadPoint(start_time=now, settlement_period=4, forecast_mw=350.0, actual_mw=300.0, error_mw=-50.0),
        DayAheadPoint(start_time=now, settlement_period=5, forecast_mw=200.0, actual_mw=250.0, error_mw=50.0),
    ]

    metrics = calculate_accuracy_metrics(points, total_expected_periods=5)

    assert metrics.evaluated_points == 5
    assert metrics.total_expected_periods == 5
    assert metrics.coverage_pct == 100.0

    # Hand calculations:
    # Bias: (-20 + 20 + 0 - 50 + 50) / 5 = 0.0 MW
    assert metrics.bias_mw == 0.0

    # MAE: (20 + 20 + 0 + 50 + 50) / 5 = 140 / 5 = 28.0 MW
    assert metrics.mae_mw == 28.0

    # RMSE: sqrt((400 + 400 + 0 + 2500 + 2500) / 5) = sqrt(5800 / 5) = sqrt(1160) = 34.0587... -> 34.06 MW
    assert metrics.rmse_mw == 34.06

    # WAPE: 140 / 1000 * 100 = 14.0%
    assert metrics.wape_pct == 14.0

    # Median absolute error: sorted abs errors [0, 20, 20, 50, 50] -> median is 20.0 MW
    assert metrics.median_abs_error_mw == 20.0

    # Shortfall frequency: 2 periods with error < 0 out of 5 = 40.0%
    assert metrics.shortfall_frequency_pct == 40.0

    # Mean shortfall magnitude: (20 + 50) / 2 = 35.0 MW
    assert metrics.mean_shortfall_mw == 35.0

    # Max shortfall: 50.0 MW
    assert metrics.max_shortfall_mw == 50.0

    # Max surplus: 50.0 MW
    assert metrics.max_surplus_mw == 50.0

    # Quantiles: sorted errors [-50, -20, 0, 20, 50] -> median (P50) is 0.0
    assert metrics.quantiles.p50 == 0.0


def test_mathematical_identities_and_invariants() -> None:
    """Verify universal mathematical relationships."""
    errors = [-300.0, -120.0, -45.0, 10.0, 80.0, 220.0, 450.0]
    now = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    points = [
        DayAheadPoint(
            start_time=now,
            settlement_period=i + 1,
            forecast_mw=1000.0,
            actual_mw=1000.0 + err,
            error_mw=err,
        )
        for i, err in enumerate(errors)
    ]

    metrics = calculate_accuracy_metrics(points, total_expected_periods=len(points))

    # Invariant 1: RMSE >= MAE always
    assert metrics.rmse_mw >= metrics.mae_mw

    # Invariant 2: Quantiles are strictly monotonic non-decreasing
    q = metrics.quantiles
    assert q.p5 <= q.p10 <= q.p25 <= q.p50 <= q.p75 <= q.p90 <= q.p95

    # Invariant 3: Shortfall frequency within [0, 100]
    assert 0.0 <= metrics.shortfall_frequency_pct <= 100.0


def test_empty_and_missing_data_edge_cases() -> None:
    """Test safe handling when all points are missing."""
    empty_metrics = calculate_accuracy_metrics([], total_expected_periods=48)
    assert empty_metrics.evaluated_points == 0
    assert empty_metrics.coverage_pct == 0.0
    assert empty_metrics.mae_mw == 0.0
    assert empty_metrics.rmse_mw == 0.0

    q = compute_quantiles([])
    assert q.p50 == 0.0


def test_histogram_distribution_properties() -> None:
    """Verify histogram bins cover full range without gaps."""
    now = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    points = [
        DayAheadPoint(
            start_time=now,
            settlement_period=i + 1,
            forecast_mw=500.0,
            actual_mw=500.0 + float(i * 10 - 200),
            error_mw=float(i * 10 - 200),
        )
        for i in range(40)
    ]

    min_err, max_err, quantiles, bins = calculate_error_distribution(points, num_bins=10)

    assert min_err < max_err
    assert len(bins) == 10
    total_count = sum(b.count for b in bins)
    assert total_count == 40

    total_freq = sum(b.frequency_pct for b in bins)
    assert 99.0 <= total_freq <= 101.0  # slight float rounding tolerance

    # Consecutive bins are contiguous
    for i in range(len(bins) - 1):
        assert bins[i].bin_end == bins[i + 1].bin_start


def test_full_month_accuracy_against_seed(memory_db_session: Session) -> None:
    """Verify evaluation runs over entire January 2026 (31 days, 1488 periods) from seed."""
    d_from = date(2026, 1, 1)
    d_to = date(2026, 1, 31)

    summary = get_accuracy_summary(memory_db_session, d_from, d_to, cutoff_str="09:00")

    assert summary.days_evaluated == 31
    assert summary.metrics.total_expected_periods == 31 * 48  # 1,488 expected half-hour settlement periods
    assert summary.metrics.evaluated_points == 31 * 24  # 744 evaluated hourly forecast periods
    assert summary.metrics.coverage_pct == 50.0

    # Realistic GB wind forecast assertions:
    assert summary.metrics.mae_mw > 0.0
    assert summary.metrics.rmse_mw >= summary.metrics.mae_mw
    assert summary.metrics.wape_pct > 0.0
    assert 0.0 < summary.metrics.shortfall_frequency_pct < 100.0

    # Check distribution
    dist = get_error_distribution(memory_db_session, d_from, d_to, cutoff_str="09:00", bins_count=20)
    assert dist.total_samples == 31 * 24
    assert len(dist.bins) == 20
    assert dist.min_error_mw < 0  # There are shortfalls
    assert dist.max_error_mw > 0  # There are surpluses
