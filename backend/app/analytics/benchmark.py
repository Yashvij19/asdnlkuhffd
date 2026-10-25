"""
Naive 24-Hour Persistence Baseline Benchmark & Skill Score Engine (FR-ACC-6).
Evaluates utility day-ahead wind forecasts against a naive persistence baseline
(actual wind generation from t - 24 hours), calculating comparative MAE, RMSE,
Bias, and WMO standard forecast Skill Scores.
"""

from datetime import UTC, date, datetime, time, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.selection import get_delivery_day_periods, select_day_ahead_forecast
from app.models import ActualWind
from app.schemas import BenchmarkPoint, PersistenceBenchmarkResult


def _to_utc_aware(dt: datetime) -> datetime:
    """Ensure datetime has tzinfo=UTC (handles SQLite naive timestamps)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def compute_persistence_benchmark(
    session: Session,
    decision_from: date,
    decision_to: date,
    cutoff_str: str = "09:00",
    tz_name: str = "Europe/London",
) -> PersistenceBenchmarkResult:
    """
    Compute naive 24h persistence benchmark and skill score comparison for a decision window.
    Evaluates only settlement periods where both forecast and persistence actuals (t - 24h) exist.
    """
    if decision_from > decision_to:
        raise ValueError(
            f"decision_from ({decision_from}) cannot be after decision_to ({decision_to})"
        )

    # 1. Determine overall query boundary for actuals (covering delivery days + 24h prior)
    delivery_from = decision_from + timedelta(days=1)
    delivery_to = decision_to + timedelta(days=1)

    periods_start = get_delivery_day_periods(delivery_from, tz_name=tz_name)
    periods_end = get_delivery_day_periods(delivery_to, tz_name=tz_name)

    if not periods_start:
        min_delivery_utc = datetime.combine(delivery_from, time(0, 0), tzinfo=UTC)
    else:
        min_delivery_utc = periods_start[0][0]

    if not periods_end:
        max_delivery_utc = datetime.combine(delivery_to, time(23, 30), tzinfo=UTC)
    else:
        max_delivery_utc = periods_end[-1][0]

    min_query_utc = min_delivery_utc - timedelta(hours=25)
    max_query_utc = max_delivery_utc + timedelta(hours=1)

    # Fetch all actual wind records across the range
    actuals_stmt = select(ActualWind).where(
        ActualWind.start_time_utc >= min_query_utc,
        ActualWind.start_time_utc <= max_query_utc,
    )
    actual_rows = session.scalars(actuals_stmt).all()
    actuals_by_utc: dict[datetime, float] = {
        _to_utc_aware(a.start_time_utc): a.generation_mw for a in actual_rows
    }

    # 2. Iterate daily and evaluate paired (Actual, Forecast, Persistence)
    curr_d = decision_from
    daily_benchmarks: list[BenchmarkPoint] = []
    days_fc_won = 0
    days_persist_won = 0

    all_actuals: list[float] = []
    all_fc_errors: list[float] = []
    all_persist_errors: list[float] = []

    while curr_d <= decision_to:
        curr_delivery = curr_d + timedelta(days=1)
        day_res = select_day_ahead_forecast(
            session=session,
            decision_date=curr_d,
            cutoff_str=cutoff_str,
            tz_name=tz_name,
        )

        d_actuals: list[float] = []
        d_fc_values: list[float] = []
        d_persist_values: list[float] = []
        d_fc_errors: list[float] = []
        d_persist_errors: list[float] = []

        for p in day_res.points:
            if p.actual_mw is None or p.forecast_mw is None:
                continue

            t_utc = _to_utc_aware(p.start_time)
            prior_24h_utc = t_utc - timedelta(hours=24)
            persist_mw = actuals_by_utc.get(prior_24h_utc)

            if persist_mw is None:
                continue

            act_mw = p.actual_mw
            fc_mw = p.forecast_mw
            fc_err = act_mw - fc_mw
            persist_err = act_mw - persist_mw

            d_actuals.append(act_mw)
            d_fc_values.append(fc_mw)
            d_persist_values.append(persist_mw)
            d_fc_errors.append(fc_err)
            d_persist_errors.append(persist_err)

            all_actuals.append(act_mw)
            all_fc_errors.append(fc_err)
            all_persist_errors.append(persist_err)

        if d_fc_errors:
            d_fc_mae = float(np.mean(np.abs(d_fc_errors)))
            d_persist_mae = float(np.mean(np.abs(d_persist_errors)))
            d_fc_rmse = float(np.sqrt(np.mean(np.square(d_fc_errors))))
            d_persist_rmse = float(np.sqrt(np.mean(np.square(d_persist_errors))))
            d_fc_bias = float(np.mean(d_fc_errors))
            d_persist_bias = float(np.mean(d_persist_errors))

            d_skill = (
                (1.0 - (d_fc_mae / d_persist_mae))
                if d_persist_mae > 0
                else 0.0
            )

            if d_fc_mae < d_persist_mae:
                days_fc_won += 1
            else:
                days_persist_won += 1

            daily_benchmarks.append(
                BenchmarkPoint(
                    delivery_date=curr_delivery.isoformat(),
                    sample_count=len(d_fc_errors),
                    mean_actual_mw=round(float(np.mean(d_actuals)), 2),
                    forecast_mean_mw=round(float(np.mean(d_fc_values)), 2),
                    persistence_mean_mw=round(float(np.mean(d_persist_values)), 2),
                    forecast_mae_mw=round(d_fc_mae, 2),
                    persistence_mae_mw=round(d_persist_mae, 2),
                    forecast_rmse_mw=round(d_fc_rmse, 2),
                    persistence_rmse_mw=round(d_persist_rmse, 2),
                    forecast_bias_mw=round(d_fc_bias, 2),
                    persistence_bias_mw=round(d_persist_bias, 2),
                    skill_score=round(d_skill, 4),
                    skill_score_pct=round(d_skill * 100.0, 2),
                )
            )

        curr_d += timedelta(days=1)

    # 3. Overall window aggregation
    if not all_fc_errors:
        return PersistenceBenchmarkResult(
            decision_from=decision_from.isoformat(),
            decision_to=decision_to.isoformat(),
            cutoff_local=cutoff_str,
            total_samples=0,
            overall_mean_actual_mw=0.0,
            forecast_mae_mw=0.0,
            persistence_mae_mw=0.0,
            forecast_rmse_mw=0.0,
            persistence_rmse_mw=0.0,
            forecast_bias_mw=0.0,
            persistence_bias_mw=0.0,
            overall_skill_score=0.0,
            overall_skill_score_pct=0.0,
            rmse_skill_score=0.0,
            days_forecast_won=0,
            days_persistence_won=0,
            daily_comparison=[],
        )

    overall_actual_mean = float(np.mean(all_actuals))
    overall_fc_mae = float(np.mean(np.abs(all_fc_errors)))
    overall_persist_mae = float(np.mean(np.abs(all_persist_errors)))
    overall_fc_rmse = float(np.sqrt(np.mean(np.square(all_fc_errors))))
    overall_persist_rmse = float(np.sqrt(np.mean(np.square(all_persist_errors))))
    overall_fc_bias = float(np.mean(all_fc_errors))
    overall_persist_bias = float(np.mean(all_persist_errors))

    overall_skill = (
        (1.0 - (overall_fc_mae / overall_persist_mae))
        if overall_persist_mae > 0
        else 0.0
    )
    overall_rmse_skill = (
        (1.0 - (overall_fc_rmse / overall_persist_rmse))
        if overall_persist_rmse > 0
        else 0.0
    )

    return PersistenceBenchmarkResult(
        decision_from=decision_from.isoformat(),
        decision_to=decision_to.isoformat(),
        cutoff_local=cutoff_str,
        total_samples=len(all_fc_errors),
        overall_mean_actual_mw=round(overall_actual_mean, 2),
        forecast_mae_mw=round(overall_fc_mae, 2),
        persistence_mae_mw=round(overall_persist_mae, 2),
        forecast_rmse_mw=round(overall_fc_rmse, 2),
        persistence_rmse_mw=round(overall_persist_rmse, 2),
        forecast_bias_mw=round(overall_fc_bias, 2),
        persistence_bias_mw=round(overall_persist_bias, 2),
        overall_skill_score=round(overall_skill, 4),
        overall_skill_score_pct=round(overall_skill * 100.0, 2),
        rmse_skill_score=round(overall_rmse_skill, 4),
        days_forecast_won=days_fc_won,
        days_persistence_won=days_persist_won,
        daily_comparison=daily_benchmarks,
    )
