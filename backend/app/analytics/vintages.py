"""
Multi-Vintage Evolution Analytics Engine.
Enables traders to analyze how day-ahead wind forecasts evolved across
successive publish timestamps leading up to delivery day.
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.selection import get_delivery_day_periods
from app.models import ActualWind, WindForecast
from app.schemas import DayAheadVintagesResult, VintageDataPoint, VintageSeries


def _to_utc_aware(dt: datetime) -> datetime:
    """Ensure datetime has tzinfo=UTC (handles SQLite naive timestamps)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_day_ahead_vintages(
    session: Session,
    delivery_date: date,
    limit_vintages: int | None = None,
    tz_name: str = "Europe/London",
) -> DayAheadVintagesResult:
    """
    Retrieve all published forecast vintages and actuals for a specific delivery day.
    Orders vintage curves chronologically to display forecast evolution trajectories.
    """
    tz = ZoneInfo(tz_name)
    periods = get_delivery_day_periods(delivery_date, tz_name=tz_name)

    if not periods:
        min_target = datetime.combine(delivery_date, time(0, 0), tzinfo=UTC)
        max_target = datetime.combine(delivery_date, time(23, 30), tzinfo=UTC)
    else:
        min_target = periods[0][0]
        max_target = periods[-1][0]

    sp_map = {p[0]: p[1] for p in periods}

    # 1. Fetch delivered actuals for the delivery day
    actuals_stmt = (
        select(ActualWind)
        .where(
            ActualWind.start_time_utc >= min_target,
            ActualWind.start_time_utc <= max_target,
        )
        .order_by(ActualWind.start_time_utc.asc())
    )
    actual_rows = session.scalars(actuals_stmt).all()
    actual_map: dict[datetime, float] = {
        _to_utc_aware(a.start_time_utc): a.generation_mw for a in actual_rows
    }

    actuals_points: list[VintageDataPoint] = []
    for t_utc, sp in periods:
        act_mw = actual_map.get(t_utc)
        if act_mw is not None:
            actuals_points.append(
                VintageDataPoint(
                    start_time=t_utc,
                    settlement_period=sp,
                    forecast_mw=0.0,
                    horizon_hours=0.0,
                    actual_mw=act_mw,
                    error_mw=0.0,
                )
            )

    # 2. Fetch all forecast rows targeting this delivery day
    forecast_stmt = (
        select(WindForecast)
        .where(
            WindForecast.start_time_utc >= min_target,
            WindForecast.start_time_utc <= max_target,
        )
        .order_by(WindForecast.publish_time_utc.asc(), WindForecast.start_time_utc.asc())
    )
    forecast_rows = session.scalars(forecast_stmt).all()

    # Group by unique publish_time_utc normalized to UTC
    vintages_dict: dict[datetime, list[tuple[datetime, WindForecast]]] = {}
    for fc in forecast_rows:
        pub_utc = _to_utc_aware(fc.publish_time_utc)
        st_utc = _to_utc_aware(fc.start_time_utc)
        if pub_utc not in vintages_dict:
            vintages_dict[pub_utc] = []
        vintages_dict[pub_utc].append((st_utc, fc))

    all_publish_times = sorted(vintages_dict.keys())
    total_vintages = len(all_publish_times)

    # Filter/sample if limit_vintages requested
    if limit_vintages is not None and 0 < limit_vintages < total_vintages:
        # Sample evenly across the timeline to show progression from D-2 to intraday
        indices = np.linspace(0, total_vintages - 1, limit_vintages, dtype=int)
        selected_publish_times = [all_publish_times[i] for i in sorted(set(indices))]
    else:
        selected_publish_times = all_publish_times

    vintage_series_list: list[VintageSeries] = []

    for pub_time in selected_publish_times:
        rows = vintages_dict[pub_time]
        pts: list[VintageDataPoint] = []
        errors: list[float] = []
        forecasts: list[float] = []

        for st_utc, r in rows:
            sp = sp_map.get(st_utc, 1)
            act_mw = actual_map.get(st_utc)
            err_mw = (act_mw - r.generation_mw) if act_mw is not None else None

            if err_mw is not None:
                errors.append(err_mw)
            forecasts.append(r.generation_mw)

            pts.append(
                VintageDataPoint(
                    start_time=st_utc,
                    settlement_period=sp,
                    forecast_mw=r.generation_mw,
                    horizon_hours=r.horizon_hours,
                    actual_mw=act_mw,
                    error_mw=round(err_mw, 1) if err_mw is not None else None,
                )
            )

        mean_fc = float(np.mean(forecasts)) if forecasts else 0.0
        mae = float(np.mean(np.abs(errors))) if errors else None
        bias = float(np.mean(errors)) if errors else None

        pub_local = pub_time.astimezone(tz)
        label = f"Publish {pub_local.strftime('%d %b %H:%M')}"

        vintage_series_list.append(
            VintageSeries(
                publish_time_utc=pub_time,
                vintage_label=label,
                points_count=len(pts),
                mean_forecast_mw=round(mean_fc, 1),
                mae_mw=round(mae, 2) if mae is not None else None,
                bias_mw=round(bias, 2) if bias is not None else None,
                points=pts,
            )
        )

    return DayAheadVintagesResult(
        delivery_date=delivery_date.isoformat(),
        total_vintages_available=total_vintages,
        returned_vintages=len(vintage_series_list),
        actuals=actuals_points,
        vintages=vintage_series_list,
    )
