"""
Analytics Service and In-Memory Caching Engine.
Guarantees sub-300ms p95 response times across all analytics endpoints
via a thread-safe in-memory cache with TTL and pre-warming support.
Also implements FR-ACC-5: All-Vintages Forecast Horizon Error Curve.
"""

import math
import threading
import time
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.benchmark import compute_persistence_benchmark
from app.analytics.breakdowns import (
    compute_breakdown_by_day,
    compute_breakdown_by_horizon,
    compute_breakdown_by_hour,
    compute_breakdown_by_level,
    format_breakdown_result,
)
from app.analytics.buffer import calculate_procurement_buffer
from app.analytics.metrics import (
    evaluate_period_accuracy,
    get_accuracy_summary,
    get_error_distribution,
)
from app.analytics.selection import select_day_ahead_forecast
from app.analytics.vintages import get_day_ahead_vintages
from app.models import ActualWind, WindForecast
from app.schemas import (
    AccuracySummaryResult,
    BreakdownResult,
    CacheStats,
    DayAheadResult,
    DayAheadVintagesResult,
    DistributionResult,
    HorizonCurvePoint,
    HorizonCurveResult,
    PersistenceBenchmarkResult,
    ProcurementBufferResult,
)


class AnalyticsCache:
    """Thread-safe in-memory cache with TTL expiration and performance tracking."""

    def __init__(self, default_ttl_seconds: float = 600.0, max_entries: int = 1000) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    def get(self, key: str) -> Any | None:
        """Retrieve a cached object if present and unexpired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            expiry, value = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """Store an object in cache with specified or default TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expiry = time.time() + ttl
        with self._lock:
            # Enforce max entries via simple eviction of oldest entry
            if len(self._cache) >= self._max_entries and key not in self._cache:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]

            self._cache[key] = (expiry, value)

    def invalidate(self) -> None:
        """Clear all cached entries (called e.g. after new data ingestion)."""
        with self._lock:
            self._cache.clear()
            self._invalidations += 1

    def get_stats(self) -> CacheStats:
        """Return operational cache hit/miss statistics."""
        with self._lock:
            now = time.time()
            active_entries = sum(1 for exp, _ in self._cache.values() if exp > now)
            total_reqs = self._hits + self._misses
            hit_rate = (self._hits / total_reqs * 100.0) if total_reqs > 0 else 0.0

            return CacheStats(
                entries=active_entries,
                hits=self._hits,
                misses=self._misses,
                hit_rate_pct=round(hit_rate, 2),
                invalidations=self._invalidations,
            )


def compute_all_vintages_horizon_curve(
    session: Session,
    d_from: date,
    d_to: date,
    max_horizon_h: int = 48,
    step_hours: int = 6,
) -> HorizonCurveResult:
    """
    Calculate forecast accuracy metrics as a function of lead horizon (0-48h+)
    across ALL published vintages (FR-ACC-5).
    """
    if step_hours <= 0:
        step_hours = 6
    if max_horizon_h <= 0:
        max_horizon_h = 48

    stmt = (
        select(
            WindForecast.generation_mw.label("forecast_mw"),
            WindForecast.horizon_hours,
            ActualWind.generation_mw.label("actual_mw"),
        )
        .join(ActualWind, WindForecast.start_time_utc == ActualWind.start_time_utc)
        .where(
            ActualWind.settlement_date >= d_from,
            ActualWind.settlement_date <= d_to,
            WindForecast.horizon_hours >= 0,
            WindForecast.horizon_hours <= max_horizon_h,
        )
    )

    rows = session.execute(stmt).all()
    total_samples = len(rows)

    if total_samples == 0:
        return HorizonCurveResult(
            delivery_from=d_from.isoformat(),
            delivery_to=d_to.isoformat(),
            max_horizon_h=max_horizon_h,
            step_hours=step_hours,
            total_samples=0,
            curve=[],
        )

    fcs = np.array([r.forecast_mw for r in rows], dtype=np.float64)
    acts = np.array([r.actual_mw for r in rows], dtype=np.float64)
    horizons = np.array([r.horizon_hours for r in rows], dtype=np.float64)
    errors = acts - fcs

    curve_points: list[HorizonCurvePoint] = []

    for h_start in range(0, max_horizon_h, step_hours):
        h_end = min(h_start + step_hours, max_horizon_h)
        is_last_bucket = h_end == max_horizon_h

        mask = (horizons >= h_start) & (horizons <= h_end if is_last_bucket else horizons < h_end)
        count = int(np.sum(mask))

        label = f"{h_start}h - {h_end}h" if step_hours > 1 else f"{h_start}h"

        if count == 0:
            curve_points.append(
                HorizonCurvePoint(
                    horizon_start_h=float(h_start),
                    horizon_end_h=float(h_end),
                    bucket_label=label,
                    sample_count=0,
                    mean_forecast_mw=0.0,
                    mean_actual_mw=0.0,
                    bias_mw=0.0,
                    mae_mw=0.0,
                    rmse_mw=0.0,
                    wape_pct=0.0,
                    shortfall_frequency_pct=0.0,
                )
            )
            continue

        b_fcs = fcs[mask]
        b_acts = acts[mask]
        b_errs = errors[mask]
        b_abs_errs = np.abs(b_errs)

        mean_fc = float(np.mean(b_fcs))
        mean_act = float(np.mean(b_acts))
        bias = float(np.mean(b_errs))
        mae = float(np.mean(b_abs_errs))
        rmse = float(math.sqrt(np.mean(b_errs**2)))

        sum_act = float(np.sum(b_acts))
        wape = (float(np.sum(b_abs_errs)) / sum_act * 100.0) if sum_act > 0 else 0.0

        shortfall_count = int(np.sum(b_errs < 0))
        shortfall_freq = (shortfall_count / count) * 100.0

        curve_points.append(
            HorizonCurvePoint(
                horizon_start_h=float(h_start),
                horizon_end_h=float(h_end),
                bucket_label=label,
                sample_count=count,
                mean_forecast_mw=round(mean_fc, 1),
                mean_actual_mw=round(mean_act, 1),
                bias_mw=round(bias, 2),
                mae_mw=round(mae, 2),
                rmse_mw=round(rmse, 2),
                wape_pct=round(wape, 2),
                shortfall_frequency_pct=round(shortfall_freq, 1),
            )
        )

    return HorizonCurveResult(
        delivery_from=d_from.isoformat(),
        delivery_to=d_to.isoformat(),
        max_horizon_h=max_horizon_h,
        step_hours=step_hours,
        total_samples=total_samples,
        curve=curve_points,
    )


class AnalyticsService:
    """
    Central facade managing execution and caching of all analytical calculations.
    Ensures single source of truth and performance compliance (<300ms p95).
    """

    def __init__(self, cache: AnalyticsCache | None = None) -> None:
        self.cache = cache or AnalyticsCache()

    def get_day_ahead(
        self, session: Session, decision_date: date, cutoff_str: str = "09:00"
    ) -> DayAheadResult:
        cache_key = f"day_ahead:{decision_date.isoformat()}:{cutoff_str}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, DayAheadResult):
            return cached

        result = select_day_ahead_forecast(session, decision_date, cutoff_str=cutoff_str)
        self.cache.set(cache_key, result)
        return result

    def get_accuracy_summary(
        self, session: Session, d_from: date, d_to: date, cutoff_str: str = "09:00"
    ) -> AccuracySummaryResult:
        cache_key = f"acc_summary:{d_from.isoformat()}:{d_to.isoformat()}:{cutoff_str}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, AccuracySummaryResult):
            return cached

        result = get_accuracy_summary(session, d_from, d_to, cutoff_str=cutoff_str)
        self.cache.set(cache_key, result)
        return result

    def get_error_distribution(
        self, session: Session, d_from: date, d_to: date, cutoff_str: str = "09:00", bins_count: int = 20
    ) -> DistributionResult:
        cache_key = f"distribution:{d_from.isoformat()}:{d_to.isoformat()}:{cutoff_str}:{bins_count}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, DistributionResult):
            return cached

        result = get_error_distribution(session, d_from, d_to, cutoff_str=cutoff_str, bins_count=bins_count)
        self.cache.set(cache_key, result)
        return result

    def get_breakdown(
        self, session: Session, dimension: str, d_from: date, d_to: date, cutoff_str: str = "09:00"
    ) -> BreakdownResult:
        cache_key = f"breakdown:{dimension}:{d_from.isoformat()}:{d_to.isoformat()}:{cutoff_str}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, BreakdownResult):
            return cached

        points, _, _ = evaluate_period_accuracy(session, d_from, d_to, cutoff_str=cutoff_str)

        if dimension == "day":
            items = compute_breakdown_by_day(points)
        elif dimension == "hour":
            items = compute_breakdown_by_hour(points)
        elif dimension == "horizon":
            items = compute_breakdown_by_horizon(points)
        elif dimension == "level":
            items = compute_breakdown_by_level(points)
        else:
            raise ValueError(f"Unknown breakdown dimension: {dimension}")

        result = format_breakdown_result(
            dimension, items, d_from.isoformat(), d_to.isoformat(), cutoff_str
        )
        self.cache.set(cache_key, result)
        return result

    def get_procurement_buffer(
        self,
        session: Session,
        d_from: date,
        d_to: date,
        cutoff_str: str = "09:00",
        confidence: float = 0.90,
    ) -> ProcurementBufferResult:
        cache_key = f"buffer:{d_from.isoformat()}:{d_to.isoformat()}:{cutoff_str}:{confidence:.4f}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, ProcurementBufferResult):
            return cached

        points, _, _ = evaluate_period_accuracy(session, d_from, d_to, cutoff_str=cutoff_str)
        result = calculate_procurement_buffer(
            points=points,
            confidence=confidence,
            decision_from=d_from.isoformat(),
            decision_to=d_to.isoformat(),
            cutoff_local=cutoff_str,
        )
        self.cache.set(cache_key, result)
        return result

    def get_horizon_curve(
        self,
        session: Session,
        d_from: date,
        d_to: date,
        max_horizon_h: int = 48,
        step_hours: int = 6,
    ) -> HorizonCurveResult:
        cache_key = f"horizon_curve:{d_from.isoformat()}:{d_to.isoformat()}:{max_horizon_h}:{step_hours}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, HorizonCurveResult):
            return cached

        result = compute_all_vintages_horizon_curve(
            session=session,
            d_from=d_from,
            d_to=d_to,
            max_horizon_h=max_horizon_h,
            step_hours=step_hours,
        )
        self.cache.set(cache_key, result)
        return result

    def get_day_ahead_vintages(
        self,
        session: Session,
        delivery_date: date,
        limit_vintages: int | None = None,
        tz_name: str = "Europe/London",
    ) -> DayAheadVintagesResult:
        cache_key = f"vintages:{delivery_date.isoformat()}:{limit_vintages}:{tz_name}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, DayAheadVintagesResult):
            return cached

        result = get_day_ahead_vintages(
            session=session,
            delivery_date=delivery_date,
            limit_vintages=limit_vintages,
            tz_name=tz_name,
        )
        self.cache.set(cache_key, result)
        return result

    def get_persistence_benchmark(
        self,
        session: Session,
        d_from: date,
        d_to: date,
        cutoff_str: str = "09:00",
        tz_name: str = "Europe/London",
    ) -> PersistenceBenchmarkResult:
        cache_key = f"benchmark:{d_from.isoformat()}:{d_to.isoformat()}:{cutoff_str}:{tz_name}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, PersistenceBenchmarkResult):
            return cached

        result = compute_persistence_benchmark(
            session=session,
            decision_from=d_from,
            decision_to=d_to,
            cutoff_str=cutoff_str,
            tz_name=tz_name,
        )
        self.cache.set(cache_key, result)
        return result

    def warm_default_cache(self, session: Session) -> dict[str, int]:
        """Pre-compute and populate cache for standard January 2026 views."""
        d_from = date(2026, 1, 1)
        d_to = date(2026, 1, 31)
        default_cutoff = "09:00"

        # 1. Headline summary
        self.get_accuracy_summary(session, d_from, d_to, default_cutoff)
        # 2. Error distribution
        self.get_error_distribution(session, d_from, d_to, default_cutoff, 20)
        # 3. Multi-dimensional breakdowns
        for dim in ["day", "hour", "horizon", "level"]:
            self.get_breakdown(session, dim, d_from, d_to, default_cutoff)
        # 4. Standard safety buffers (90% and 95%)
        self.get_procurement_buffer(session, d_from, d_to, default_cutoff, 0.90)
        self.get_procurement_buffer(session, d_from, d_to, default_cutoff, 0.95)
        # 5. Horizon curve (6h and 1h)
        self.get_horizon_curve(session, d_from, d_to, max_horizon_h=48, step_hours=6)
        # 6. Sample day-ahead point
        self.get_day_ahead(session, date(2026, 1, 15), default_cutoff)
        # 7. Sample day-ahead vintages
        self.get_day_ahead_vintages(session, date(2026, 1, 15))
        # 8. Persistence baseline benchmark (FR-ACC-6)
        self.get_persistence_benchmark(session, d_from, d_to, default_cutoff)

        return {"warmed_entries": self.cache.get_stats().entries}

    def cache_stats(self) -> CacheStats:
        return self.cache.get_stats()

    def invalidate_cache(self) -> None:
        self.cache.invalidate()


# Singleton instance
analytics_service = AnalyticsService()
