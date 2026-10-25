"""
Day-Ahead Wind Forecast Selection Algorithm.
For a delivery day D and cut-off C on D-1, selects the latest forecast vintage
published at or before the cut-off for each 30-minute settlement period,
pairs with actual generation, and computes lead time horizon and forecast error.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ActualWind, WindForecast
from app.schemas import (
    DayAheadCoverage,
    DayAheadPoint,
    DayAheadResult,
    DayAheadSummary,
)


def compute_decision_cutoff_utc(
    decision_date: date, cutoff_str: str, tz_name: str = "Europe/London"
) -> datetime:
    """
    Compute exact UTC timestamp for the decision cut-off time on decision day (D-1).
    Local time in tz_name (e.g. 09:00 London time) is converted to UTC.
    """
    hour_str, minute_str = cutoff_str.split(":")
    cutoff_time = time(hour=int(hour_str), minute=int(minute_str))

    tz = ZoneInfo(tz_name)
    local_dt = datetime.combine(decision_date, cutoff_time, tzinfo=tz)
    return local_dt.astimezone(UTC)


def get_delivery_day_periods(
    delivery_date: date, tz_name: str = "Europe/London"
) -> list[tuple[datetime, int]]:
    """
    Return all expected 30-minute settlement periods for a delivery date in market timezone.
    Returns list of (start_time_utc, settlement_period_number).
    Normally 48 periods per day (46/50 on clock-change days).
    """
    tz = ZoneInfo(tz_name)
    local_start = datetime.combine(delivery_date, time(0, 0), tzinfo=tz)
    next_day_local = datetime.combine(delivery_date + timedelta(days=1), time(0, 0), tzinfo=tz)

    periods: list[tuple[datetime, int]] = []
    current_local = local_start
    period_num = 1

    while current_local < next_day_local:
        start_utc = current_local.astimezone(UTC)
        periods.append((start_utc, period_num))
        current_local += timedelta(minutes=30)
        period_num += 1

    return periods


def select_day_ahead_forecast(
    session: Session,
    decision_date: date,
    cutoff_str: str | None = None,
    tz_name: str | None = None,
) -> DayAheadResult:
    """
    Core Selection Logic:
    1. Delivery day D is always decision_date + 1 day.
    2. Decision cut-off is evaluated on decision_date (D-1) at cutoff_str in tz_name.
    3. For each 30-min period of day D, select the forecast vintage with max(publish_time_utc) <= cutoff_utc.
    4. Pair with actual wind generation and compute horizon (hours) and error (MW).
    """
    settings = get_settings()
    cutoff_time_str = cutoff_str or settings.default_cutoff
    timezone_name = tz_name or settings.timezone

    delivery_date = decision_date + timedelta(days=1)
    cutoff_utc = compute_decision_cutoff_utc(decision_date, cutoff_time_str, timezone_name)
    target_periods = get_delivery_day_periods(delivery_date, timezone_name)

    if not target_periods:
        min_target = datetime.combine(delivery_date, time(0, 0), tzinfo=UTC)
        max_target = datetime.combine(delivery_date, time(23, 30), tzinfo=UTC)
    else:
        min_target = target_periods[0][0]
        max_target = target_periods[-1][0]

    # Query all candidate forecasts published at or before cut-off
    stmt_fc = (
        select(WindForecast)
        .where(
            WindForecast.start_time_utc >= min_target,
            WindForecast.start_time_utc <= max_target,
            WindForecast.publish_time_utc <= cutoff_utc,
        )
        .order_by(WindForecast.start_time_utc, WindForecast.publish_time_utc.desc())
    )
    candidate_forecasts = session.scalars(stmt_fc).all()

    # Group by start_time_utc and pick latest vintage (first due to ORDER BY publish_time_utc DESC)
    latest_forecasts_by_target: dict[datetime, WindForecast] = {}
    for fc in candidate_forecasts:
        # Normalize start_time_utc to UTC timezone
        st = fc.start_time_utc
        if st.tzinfo is None:
            st = st.replace(tzinfo=UTC)
        else:
            st = st.astimezone(UTC)

        if st not in latest_forecasts_by_target:
            latest_forecasts_by_target[st] = fc

    # Query actual wind generation for delivery day targets
    stmt_act = select(ActualWind).where(
        ActualWind.start_time_utc >= min_target,
        ActualWind.start_time_utc <= max_target,
    )
    actuals = session.scalars(stmt_act).all()
    actuals_by_target: dict[datetime, ActualWind] = {}
    for act in actuals:
        st = act.start_time_utc
        if st.tzinfo is None:
            st = st.replace(tzinfo=UTC)
        else:
            st = st.astimezone(UTC)
        actuals_by_target[st] = act

    # Construct points for each settlement period
    points: list[DayAheadPoint] = []
    errors: list[float] = []
    forecast_mw_values: list[float] = []
    actual_mw_values: list[float] = []

    for target_utc, period_num in target_periods:
        selected_fc = latest_forecasts_by_target.get(target_utc)
        matched_act = actuals_by_target.get(target_utc)

        forecast_mw: float | None = None
        forecast_publish_utc: datetime | None = None
        horizon_hours: float | None = None
        actual_mw: float | None = None
        error_mw: float | None = None

        if selected_fc is not None:
            forecast_mw = selected_fc.generation_mw
            forecast_mw_values.append(forecast_mw)

            pub = selected_fc.publish_time_utc
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=UTC)
            else:
                pub = pub.astimezone(UTC)
            forecast_publish_utc = pub

            # Horizon: lead time in hours
            horizon_hours = (target_utc - pub).total_seconds() / 3600.0

        if matched_act is not None:
            actual_mw = matched_act.generation_mw
            actual_mw_values.append(actual_mw)

        # Sign convention: error = actual - forecast (negative = shortfall)
        if actual_mw is not None and forecast_mw is not None:
            error_mw = actual_mw - forecast_mw
            errors.append(error_mw)

        point = DayAheadPoint(
            start_time=target_utc,
            settlement_period=period_num,
            forecast_mw=forecast_mw,
            forecast_publish_time=forecast_publish_utc,
            horizon_hours=horizon_hours,
            actual_mw=actual_mw,
            error_mw=error_mw,
        )
        points.append(point)

    # Compute Coverage
    total_periods = len(target_periods)
    with_forecast = len(forecast_mw_values)
    with_actual = len(actual_mw_values)
    coverage_pct = (with_forecast / total_periods * 100.0) if total_periods > 0 else 0.0

    coverage = DayAheadCoverage(
        periods=total_periods,
        with_forecast=with_forecast,
        with_actual=with_actual,
        coverage_pct=round(coverage_pct, 1),
    )

    # Compute Summary
    forecast_mwh = sum(forecast_mw_values) * 0.5 if forecast_mw_values else None
    actual_mwh = sum(actual_mw_values) * 0.5 if actual_mw_values else None
    mae_mw = (sum(abs(e) for e in errors) / len(errors)) if errors else None
    bias_mw = (sum(errors) / len(errors)) if errors else None

    summary = DayAheadSummary(
        forecast_mwh=round(forecast_mwh, 1) if forecast_mwh is not None else None,
        actual_mwh=round(actual_mwh, 1) if actual_mwh is not None else None,
        mae_mw=round(mae_mw, 2) if mae_mw is not None else None,
        bias_mw=round(bias_mw, 2) if bias_mw is not None else None,
    )

    return DayAheadResult(
        decision_date=decision_date.isoformat(),
        delivery_date=delivery_date.isoformat(),
        cutoff_local=cutoff_time_str,
        cutoff_utc=cutoff_utc,
        coverage=coverage,
        summary=summary,
        points=points,
    )
