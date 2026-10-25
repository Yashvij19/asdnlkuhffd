"""
Procurement Safety Margin Buffer Engine.
Implements the safety margin logic for the utility day-ahead purchasing desk:
For a chosen confidence level c (default 90%):
- error quantile level: q = 1 - c (e.g. 10th percentile of error for 90% confidence)
- safety buffer: buffer = max(0.0, -quantile(error, 1 - c))
- risk-adjusted wind: risk_adjusted = max(0.0, forecast - buffer)

Guarantees that delivered wind meets or exceeds the risk-adjusted generation
with empirical probability >= c.
"""

from zoneinfo import ZoneInfo

import numpy as np

from app.schemas import DayAheadPoint, HourlyBufferPoint, ProcurementBufferResult


def calculate_procurement_buffer(
    points: list[DayAheadPoint],
    confidence: float = 0.90,
    decision_from: str = "2026-01-01",
    decision_to: str = "2026-01-31",
    cutoff_local: str = "09:00",
    tz_name: str = "Europe/London",
) -> ProcurementBufferResult:
    """
    Calculate overall and hour-of-day specific procurement safety buffers
    at the specified confidence level c in [0.50, 0.99].
    """
    if not (0.50 <= confidence <= 0.99):
        raise ValueError(f"Confidence must be between 0.50 and 0.99, got {confidence}")

    quantile_level = 1.0 - confidence  # e.g. 0.10 for 90% confidence

    valid_points = [
        p
        for p in points
        if p.error_mw is not None and p.forecast_mw is not None and p.actual_mw is not None
    ]

    total_samples = len(valid_points)

    if total_samples == 0:
        empty_hourly = [
            HourlyBufferPoint(
                hour=h,
                hour_label=f"{h:02d}:00 - {h+1:02d}:00",
                sample_count=0,
                buffer_mw=0.0,
                mean_forecast_mw=0.0,
                risk_adjusted_wind_mw=0.0,
            )
            for h in range(24)
        ]
        return ProcurementBufferResult(
            decision_from=decision_from,
            decision_to=decision_to,
            cutoff_local=cutoff_local,
            confidence=confidence,
            confidence_pct=round(confidence * 100.0, 1),
            total_samples=0,
            overall_buffer_mw=0.0,
            overall_mean_forecast_mw=0.0,
            overall_risk_adjusted_mw=0.0,
            hourly_buffers=empty_hourly,
        )

    # 1. Overall Buffer
    errors = np.array([p.error_mw for p in valid_points], dtype=np.float64)
    forecasts = np.array([p.forecast_mw for p in valid_points], dtype=np.float64)

    overall_q_err = float(np.percentile(errors, quantile_level * 100.0, method="linear"))
    overall_buffer = max(0.0, -overall_q_err)
    overall_mean_fc = float(np.mean(forecasts))
    overall_risk_adj = max(0.0, overall_mean_fc - overall_buffer)

    # 2. Hourly Buffers (0..23 in local market time)
    tz = ZoneInfo(tz_name)
    hourly_buckets: dict[int, list[DayAheadPoint]] = {h: [] for h in range(24)}

    for p in valid_points:
        local_hour = p.start_time.astimezone(tz).hour
        hourly_buckets[local_hour].append(p)

    hourly_buffers: list[HourlyBufferPoint] = []
    for h in range(24):
        h_points = hourly_buckets[h]
        if not h_points:
            hourly_buffers.append(
                HourlyBufferPoint(
                    hour=h,
                    hour_label=f"{h:02d}:00 - {h+1:02d}:00",
                    sample_count=0,
                    buffer_mw=0.0,
                    mean_forecast_mw=0.0,
                    risk_adjusted_wind_mw=0.0,
                )
            )
            continue

        h_errors = np.array([p.error_mw for p in h_points], dtype=np.float64)
        h_fcs = np.array([p.forecast_mw for p in h_points], dtype=np.float64)

        h_q_err = float(np.percentile(h_errors, quantile_level * 100.0, method="linear"))
        h_buffer = max(0.0, -h_q_err)
        h_mean_fc = float(np.mean(h_fcs))
        h_risk_adj = max(0.0, h_mean_fc - h_buffer)

        hourly_buffers.append(
            HourlyBufferPoint(
                hour=h,
                hour_label=f"{h:02d}:00 - {h+1:02d}:00",
                sample_count=len(h_points),
                buffer_mw=round(h_buffer, 1),
                mean_forecast_mw=round(h_mean_fc, 1),
                risk_adjusted_wind_mw=round(h_risk_adj, 1),
            )
        )

    return ProcurementBufferResult(
        decision_from=decision_from,
        decision_to=decision_to,
        cutoff_local=cutoff_local,
        confidence=confidence,
        confidence_pct=round(confidence * 100.0, 1),
        total_samples=total_samples,
        overall_buffer_mw=round(overall_buffer, 1),
        overall_mean_forecast_mw=round(overall_mean_fc, 1),
        overall_risk_adjusted_mw=round(overall_risk_adj, 1),
        hourly_buffers=hourly_buffers,
    )
