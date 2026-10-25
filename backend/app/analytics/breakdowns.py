"""
Breakdowns Analytics Engine.
Calculates forecast error and accuracy metrics sliced across dimensions:
- By Delivery Day (D)
- By Hour of Day (00:00 to 23:00 local time)
- By Forecast Horizon Lead Time (e.g. 12-18h, 18-24h, 24-30h, 30-36h, 36-42h, 42-48h+)
- By Wind Generation Level (Low, Medium-Low, Medium-High, High)
- By Weekday vs Weekend
"""

import math
from collections.abc import Callable
from zoneinfo import ZoneInfo

import numpy as np

from app.schemas import BreakdownPoint, BreakdownResult, DayAheadPoint


def _compute_point_slice(
    points: list[DayAheadPoint], key: str, label: str
) -> BreakdownPoint:
    """Compute summary accuracy metrics for a filtered subset of DayAheadPoints."""
    valid_points = [
        p
        for p in points
        if p.error_mw is not None and p.actual_mw is not None and p.forecast_mw is not None
    ]

    count = len(valid_points)
    if count == 0:
        return BreakdownPoint(
            dimension_key=key,
            dimension_label=label,
            count=0,
            mean_forecast_mw=0.0,
            mean_actual_mw=0.0,
            bias_mw=0.0,
            mae_mw=0.0,
            rmse_mw=0.0,
            wape_pct=0.0,
            shortfall_frequency_pct=0.0,
        )

    forecasts = np.array([p.forecast_mw for p in valid_points], dtype=np.float64)
    actuals = np.array([p.actual_mw for p in valid_points], dtype=np.float64)
    errors = np.array([p.error_mw for p in valid_points], dtype=np.float64)
    abs_errors = np.abs(errors)

    mean_forecast = float(np.mean(forecasts))
    mean_actual = float(np.mean(actuals))
    bias = float(np.mean(errors))
    mae = float(np.mean(abs_errors))
    rmse = float(math.sqrt(np.mean(errors**2)))

    sum_actual = float(np.sum(actuals))
    wape = (float(np.sum(abs_errors)) / sum_actual * 100.0) if sum_actual > 0 else 0.0

    shortfall_count = int(np.sum(errors < 0))
    shortfall_freq = (shortfall_count / count) * 100.0

    return BreakdownPoint(
        dimension_key=key,
        dimension_label=label,
        count=count,
        mean_forecast_mw=round(mean_forecast, 1),
        mean_actual_mw=round(mean_actual, 1),
        bias_mw=round(bias, 2),
        mae_mw=round(mae, 2),
        rmse_mw=round(rmse, 2),
        wape_pct=round(wape, 2),
        shortfall_frequency_pct=round(shortfall_freq, 1),
    )


def compute_breakdown_by_day(
    points: list[DayAheadPoint], tz_name: str = "Europe/London"
) -> list[BreakdownPoint]:
    """Group points by delivery day (YYYY-MM-DD)."""
    tz = ZoneInfo(tz_name)
    grouped: dict[str, list[DayAheadPoint]] = {}

    for p in points:
        local_dt = p.start_time.astimezone(tz)
        day_str = local_dt.date().isoformat()
        grouped.setdefault(day_str, []).append(p)

    sorted_days = sorted(grouped.keys())
    return [
        _compute_point_slice(grouped[d], key=d, label=f"Delivery Day {d}")
        for d in sorted_days
    ]


def compute_breakdown_by_hour(
    points: list[DayAheadPoint], tz_name: str = "Europe/London"
) -> list[BreakdownPoint]:
    """Group points by hour of day (0..23 in local London time)."""
    tz = ZoneInfo(tz_name)
    grouped: dict[int, list[DayAheadPoint]] = {h: [] for h in range(24)}

    for p in points:
        local_dt = p.start_time.astimezone(tz)
        grouped[local_dt.hour].append(p)

    items: list[BreakdownPoint] = []
    for h in range(24):
        key = f"{h:02d}"
        label = f"{h:02d}:00 - {h+1:02d}:00"
        items.append(_compute_point_slice(grouped[h], key=key, label=label))

    return items


def compute_breakdown_by_horizon(
    points: list[DayAheadPoint],
) -> list[BreakdownPoint]:
    """Group points by forecast lead time horizon buckets."""
    buckets: list[tuple[str, Callable[[float], bool]]] = [
        ("< 18h", lambda h: h < 18.0),
        ("18h - 24h", lambda h: 18.0 <= h < 24.0),
        ("24h - 30h", lambda h: 24.0 <= h < 30.0),
        ("30h - 36h", lambda h: 30.0 <= h < 36.0),
        ("36h - 42h", lambda h: 36.0 <= h < 42.0),
        (">= 42h", lambda h: h >= 42.0),
    ]

    items: list[BreakdownPoint] = []
    for label, condition in buckets:
        matching = [
            p
            for p in points
            if p.horizon_hours is not None and condition(p.horizon_hours)
        ]
        items.append(_compute_point_slice(matching, key=label, label=f"Lead Horizon {label}"))

    return items


def compute_breakdown_by_level(
    points: list[DayAheadPoint],
) -> list[BreakdownPoint]:
    """Group points by forecast generation power level tiers."""
    tiers: list[tuple[str, str, Callable[[float], bool]]] = [
        ("0-5k MW", "Low Wind (0 - 5,000 MW)", lambda mw: mw < 5000.0),
        ("5k-10k MW", "Med-Low Wind (5,000 - 10,000 MW)", lambda mw: 5000.0 <= mw < 10000.0),
        ("10k-15k MW", "Med-High Wind (10,000 - 15,000 MW)", lambda mw: 10000.0 <= mw < 15000.0),
        ("> 15k MW", "High Wind (> 15,000 MW)", lambda mw: mw >= 15000.0),
    ]

    items: list[BreakdownPoint] = []
    for key, label, condition in tiers:
        matching = [
            p
            for p in points
            if p.forecast_mw is not None and condition(p.forecast_mw)
        ]
        items.append(_compute_point_slice(matching, key=key, label=label))

    return items


def compute_breakdown_by_weekday(
    points: list[DayAheadPoint], tz_name: str = "Europe/London"
) -> list[BreakdownPoint]:
    """Group points by Weekday (Monday-Friday) vs Weekend (Saturday-Sunday)."""
    tz = ZoneInfo(tz_name)
    weekdays: list[DayAheadPoint] = []
    weekends: list[DayAheadPoint] = []

    for p in points:
        local_dt = p.start_time.astimezone(tz)
        if local_dt.weekday() < 5:
            weekdays.append(p)
        else:
            weekends.append(p)

    return [
        _compute_point_slice(weekdays, key="weekday", label="Weekday (Mon - Fri)"),
        _compute_point_slice(weekends, key="weekend", label="Weekend (Sat - Sun)"),
    ]


def format_breakdown_result(
    dimension: str,
    items: list[BreakdownPoint],
    decision_from: str,
    decision_to: str,
    cutoff_local: str,
) -> BreakdownResult:
    """Wrap breakdown items in BreakdownResult schema."""
    return BreakdownResult(
        dimension=dimension,
        decision_from=decision_from,
        decision_to=decision_to,
        cutoff_local=cutoff_local,
        items=items,
    )
