"""
Headline Accuracy Metrics & Error Distribution Engine.
Computes quantitative forecast evaluation metrics:
- Bias (mean error), MAE, RMSE, WAPE
- Median absolute error, P90 absolute error
- Shortfall frequency (% of periods where actual < forecast)
- Mean shortfall magnitude, max shortfall magnitude, max surplus
- Error quantiles (P5 through P95)
- Histogram error distribution bins
"""

import math
from datetime import date, timedelta
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.analytics.selection import select_day_ahead_forecast
from app.schemas import (
    AccuracyMetrics,
    AccuracyQuantiles,
    AccuracySummaryResult,
    DayAheadPoint,
    DistributionResult,
    HistogramBin,
)


def compute_quantiles(errors: list[float] | np.ndarray[Any, Any]) -> AccuracyQuantiles:
    """Compute P5, P10, P25, P50, P75, P90, P95 error quantiles."""
    if len(errors) == 0:
        return AccuracyQuantiles(
            p5=0.0, p10=0.0, p25=0.0, p50=0.0, p75=0.0, p90=0.0, p95=0.0
        )

    arr = np.asarray(errors, dtype=np.float64)
    q_vals = np.percentile(arr, [5, 10, 25, 50, 75, 90, 95], method="linear")

    return AccuracyQuantiles(
        p5=round(float(q_vals[0]), 2),
        p10=round(float(q_vals[1]), 2),
        p25=round(float(q_vals[2]), 2),
        p50=round(float(q_vals[3]), 2),
        p75=round(float(q_vals[4]), 2),
        p90=round(float(q_vals[5]), 2),
        p95=round(float(q_vals[6]), 2),
    )


def calculate_accuracy_metrics(
    points: list[DayAheadPoint], total_expected_periods: int
) -> AccuracyMetrics:
    """
    Compute comprehensive headline accuracy metrics from evaluated settlement periods.
    Sign convention: error = actual - forecast (negative = shortfall).
    """
    valid_points = [
        p
        for p in points
        if p.error_mw is not None and p.actual_mw is not None and p.forecast_mw is not None
    ]

    evaluated_count = len(valid_points)
    coverage_pct = (
        (evaluated_count / total_expected_periods * 100.0)
        if total_expected_periods > 0
        else 0.0
    )

    if evaluated_count == 0:
        empty_q = AccuracyQuantiles(
            p5=0.0, p10=0.0, p25=0.0, p50=0.0, p75=0.0, p90=0.0, p95=0.0
        )
        return AccuracyMetrics(
            evaluated_points=0,
            total_expected_periods=total_expected_periods,
            coverage_pct=0.0,
            bias_mw=0.0,
            mae_mw=0.0,
            rmse_mw=0.0,
            wape_pct=0.0,
            median_abs_error_mw=0.0,
            p90_abs_error_mw=0.0,
            shortfall_frequency_pct=0.0,
            mean_shortfall_mw=0.0,
            max_shortfall_mw=0.0,
            max_surplus_mw=0.0,
            quantiles=empty_q,
        )

    errors = np.array([p.error_mw for p in valid_points], dtype=np.float64)
    actuals = np.array([p.actual_mw for p in valid_points], dtype=np.float64)
    abs_errors = np.abs(errors)

    bias_mw = float(np.mean(errors))
    mae_mw = float(np.mean(abs_errors))
    rmse_mw = float(math.sqrt(np.mean(errors**2)))

    # WAPE: sum(|actual - forecast|) / sum(actual) * 100
    sum_actuals = float(np.sum(actuals))
    wape_pct = (float(np.sum(abs_errors)) / sum_actuals * 100.0) if sum_actuals > 0 else 0.0

    # Percentiles of absolute error
    median_abs_error_mw = float(np.median(abs_errors))
    p90_abs_error_mw = float(np.percentile(abs_errors, 90, method="linear"))

    # Shortfall metrics: error < 0 (actual < forecast, wind underperformed)
    shortfall_errors = errors[errors < 0]
    shortfall_count = len(shortfall_errors)
    shortfall_frequency_pct = (shortfall_count / evaluated_count) * 100.0

    # Magnitude of shortfall is |error|
    mean_shortfall_mw = float(np.mean(np.abs(shortfall_errors))) if shortfall_count > 0 else 0.0
    max_shortfall_mw = float(np.max(np.abs(shortfall_errors))) if shortfall_count > 0 else 0.0

    # Surplus metrics: error > 0 (actual > forecast, wind overdelivered)
    surplus_errors = errors[errors > 0]
    max_surplus_mw = float(np.max(surplus_errors)) if len(surplus_errors) > 0 else 0.0

    quantiles = compute_quantiles(errors)

    return AccuracyMetrics(
        evaluated_points=evaluated_count,
        total_expected_periods=total_expected_periods,
        coverage_pct=round(coverage_pct, 1),
        bias_mw=round(bias_mw, 2),
        mae_mw=round(mae_mw, 2),
        rmse_mw=round(rmse_mw, 2),
        wape_pct=round(wape_pct, 2),
        median_abs_error_mw=round(median_abs_error_mw, 2),
        p90_abs_error_mw=round(p90_abs_error_mw, 2),
        shortfall_frequency_pct=round(shortfall_frequency_pct, 1),
        mean_shortfall_mw=round(mean_shortfall_mw, 2),
        max_shortfall_mw=round(max_shortfall_mw, 2),
        max_surplus_mw=round(max_surplus_mw, 2),
        quantiles=quantiles,
    )


def calculate_error_distribution(
    points: list[DayAheadPoint], num_bins: int = 20
) -> tuple[float, float, AccuracyQuantiles, list[HistogramBin]]:
    """
    Compute error distribution histogram bins and quantiles from evaluated settlement periods.
    """
    valid_errors = [p.error_mw for p in points if p.error_mw is not None]
    if not valid_errors:
        empty_q = AccuracyQuantiles(
            p5=0.0, p10=0.0, p25=0.0, p50=0.0, p75=0.0, p90=0.0, p95=0.0
        )
        return 0.0, 0.0, empty_q, []

    arr = np.asarray(valid_errors, dtype=np.float64)
    min_err = float(np.min(arr))
    max_err = float(np.max(arr))
    quantiles = compute_quantiles(arr)

    counts, bin_edges = np.histogram(arr, bins=num_bins)
    total_count = len(arr)

    bins: list[HistogramBin] = []
    for i in range(len(counts)):
        b_start = float(bin_edges[i])
        b_end = float(bin_edges[i + 1])
        b_center = (b_start + b_end) / 2.0
        c = int(counts[i])
        freq = (c / total_count * 100.0) if total_count > 0 else 0.0

        bins.append(
            HistogramBin(
                bin_start=round(b_start, 2),
                bin_end=round(b_end, 2),
                bin_center=round(b_center, 2),
                count=c,
                frequency_pct=round(freq, 2),
            )
        )

    return round(min_err, 2), round(max_err, 2), quantiles, bins


def evaluate_period_accuracy(
    session: Session,
    decision_from: date,
    decision_to: date,
    cutoff_str: str = "09:00",
    tz_name: str = "Europe/London",
) -> tuple[list[DayAheadPoint], int, int]:
    """
    Evaluate day-ahead forecasts across all decision dates in [decision_from, decision_to].
    Returns (all_points, total_expected_periods, days_count).
    """
    if decision_from > decision_to:
        raise ValueError(f"decision_from ({decision_from}) cannot be after decision_to ({decision_to})")

    curr_d = decision_from
    all_points: list[DayAheadPoint] = []
    total_expected = 0
    days_count = 0

    while curr_d <= decision_to:
        day_res = select_day_ahead_forecast(
            session=session,
            decision_date=curr_d,
            cutoff_str=cutoff_str,
            tz_name=tz_name,
        )
        all_points.extend(day_res.points)
        total_expected += day_res.coverage.periods
        days_count += 1
        curr_d += timedelta(days=1)

    return all_points, total_expected, days_count


def get_accuracy_summary(
    session: Session,
    decision_from: date,
    decision_to: date,
    cutoff_str: str = "09:00",
    tz_name: str = "Europe/London",
) -> AccuracySummaryResult:
    """Generate complete AccuracySummaryResult for a decision window."""
    points, total_expected, days_count = evaluate_period_accuracy(
        session, decision_from, decision_to, cutoff_str, tz_name
    )

    metrics = calculate_accuracy_metrics(points, total_expected)

    delivery_from = decision_from + timedelta(days=1)
    delivery_to = decision_to + timedelta(days=1)

    return AccuracySummaryResult(
        decision_from=decision_from.isoformat(),
        decision_to=decision_to.isoformat(),
        delivery_from=delivery_from.isoformat(),
        delivery_to=delivery_to.isoformat(),
        cutoff_local=cutoff_str,
        days_evaluated=days_count,
        metrics=metrics,
    )


def get_error_distribution(
    session: Session,
    decision_from: date,
    decision_to: date,
    cutoff_str: str = "09:00",
    bins_count: int = 20,
    tz_name: str = "Europe/London",
) -> DistributionResult:
    """Generate complete DistributionResult for a decision window."""
    points, _, _ = evaluate_period_accuracy(
        session, decision_from, decision_to, cutoff_str, tz_name
    )

    min_err, max_err, quantiles, bins = calculate_error_distribution(points, num_bins=bins_count)

    valid_count = sum(b.count for b in bins)

    return DistributionResult(
        decision_from=decision_from.isoformat(),
        decision_to=decision_to.isoformat(),
        cutoff_local=cutoff_str,
        total_samples=valid_count,
        min_error_mw=min_err,
        max_error_mw=max_err,
        quantiles=quantiles,
        bins=bins,
    )
