"""
Unit tests for AnalyticsCache, AnalyticsService, and All-Vintages Horizon Curve (FR-ACC-5).
"""

import time
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.analytics.service import (
    AnalyticsCache,
    AnalyticsService,
    compute_all_vintages_horizon_curve,
)
from app.models import ActualWind, WindForecast
from app.schemas import AccuracySummaryResult, HorizonCurveResult


def test_analytics_cache_basic_operations() -> None:
    cache = AnalyticsCache(default_ttl_seconds=10.0, max_entries=10)

    # Initial stats
    stats = cache.get_stats()
    assert stats.entries == 0
    assert stats.hits == 0
    assert stats.misses == 0

    # Miss on empty
    val = cache.get("key1")
    assert val is None
    assert cache.get_stats().misses == 1

    # Set and Hit
    cache.set("key1", {"data": 123})
    assert cache.get_stats().entries == 1

    hit_val = cache.get("key1")
    assert hit_val == {"data": 123}
    assert cache.get_stats().hits == 1
    assert cache.get_stats().hit_rate_pct == 50.0  # 1 hit, 1 miss


def test_analytics_cache_expiration() -> None:
    cache = AnalyticsCache(default_ttl_seconds=0.05, max_entries=10)
    cache.set("temp", "value")

    assert cache.get("temp") == "value"
    time.sleep(0.06)

    # Should have expired
    assert cache.get("temp") is None
    assert cache.get_stats().entries == 0


def test_analytics_cache_invalidation() -> None:
    cache = AnalyticsCache(default_ttl_seconds=60.0)
    cache.set("k1", 1)
    cache.set("k2", 2)
    assert cache.get_stats().entries == 2

    cache.invalidate()
    assert cache.get_stats().entries == 0
    assert cache.get_stats().invalidations == 1
    assert cache.get("k1") is None


def test_analytics_cache_max_entries_eviction() -> None:
    cache = AnalyticsCache(default_ttl_seconds=60.0, max_entries=3)
    cache.set("k1", 1)
    cache.set("k2", 2)
    cache.set("k3", 3)
    assert cache.get_stats().entries == 3

    # Add 4th item -> should evict one
    cache.set("k4", 4)
    assert cache.get_stats().entries == 3
    assert cache.get("k4") == 4


def test_compute_all_vintages_horizon_curve(memory_db_session: Session) -> None:
    # Seed 3 delivery periods on 2026-01-02
    t1 = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, 13, 0, tzinfo=UTC)

    # Actuals
    memory_db_session.add(
        ActualWind(
            start_time_utc=t1,
            settlement_date=date(2026, 1, 2),
            settlement_period=25,
            generation_mw=1000.0,
            source_publish_time_utc=t1,
        )
    )
    memory_db_session.add(
        ActualWind(
            start_time_utc=t2,
            settlement_date=date(2026, 1, 2),
            settlement_period=27,
            generation_mw=1200.0,
            source_publish_time_utc=t2,
        )
    )

    # Forecast vintages with varying horizons:
    # For t1:
    # Vintage 1: published 4h before -> horizon 4h (actual 1000, fc 1100 -> err -100)
    p_4h = datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(
            start_time_utc=t1,
            publish_time_utc=p_4h,
            generation_mw=1100.0,
            horizon_hours=4.0,
        )
    )
    # Vintage 2: published 24h before -> horizon 24h (actual 1000, fc 1300 -> err -300)
    p_24h = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(
            start_time_utc=t1,
            publish_time_utc=p_24h,
            generation_mw=1300.0,
            horizon_hours=24.0,
        )
    )

    # For t2:
    # Vintage 3: published 5h before -> horizon 5h (actual 1200, fc 1150 -> err +50)
    p_5h = datetime(2026, 1, 2, 8, 0, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(
            start_time_utc=t2,
            publish_time_utc=p_5h,
            generation_mw=1150.0,
            horizon_hours=5.0,
        )
    )
    memory_db_session.commit()

    result = compute_all_vintages_horizon_curve(
        session=memory_db_session,
        d_from=date(2026, 1, 2),
        d_to=date(2026, 1, 2),
        max_horizon_h=48,
        step_hours=6,
    )

    assert isinstance(result, HorizonCurveResult)
    assert result.total_samples == 3
    assert len(result.curve) == 8  # 48 / 6 = 8 buckets

    # 0h - 6h bucket should have 2 samples (horizon 4h and 5h)
    b0_6 = result.curve[0]
    assert b0_6.bucket_label == "0h - 6h"
    assert b0_6.sample_count == 2
    # errors: -100 and +50 -> bias = -25.0, MAE = 75.0
    assert b0_6.bias_mw == -25.0
    assert b0_6.mae_mw == 75.0

    # 24h - 30h bucket should have 1 sample (horizon 24h)
    b24_30 = result.curve[4]
    assert b24_30.sample_count == 1
    assert b24_30.bias_mw == -300.0
    assert b24_30.mae_mw == 300.0


def test_analytics_service_caching_and_facade(memory_db_session: Session) -> None:
    # Seed sample delivery day
    t1 = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)
    p1 = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)

    memory_db_session.add(
        ActualWind(
            start_time_utc=t1,
            settlement_date=date(2026, 1, 2),
            settlement_period=21,
            generation_mw=5000.0,
            source_publish_time_utc=t1,
        )
    )
    memory_db_session.add(
        WindForecast(
            start_time_utc=t1,
            publish_time_utc=p1,
            generation_mw=5200.0,
            horizon_hours=26.0,
        )
    )
    memory_db_session.commit()

    service = AnalyticsService(cache=AnalyticsCache())

    # Call summary first time -> cache miss
    res1 = service.get_accuracy_summary(
        memory_db_session, date(2026, 1, 1), date(2026, 1, 1), cutoff_str="09:00"
    )
    assert isinstance(res1, AccuracySummaryResult)
    assert service.cache.get_stats().hits == 0
    assert service.cache.get_stats().misses == 1

    # Call summary second time -> cache hit
    res2 = service.get_accuracy_summary(
        memory_db_session, date(2026, 1, 1), date(2026, 1, 1), cutoff_str="09:00"
    )
    assert res2.days_evaluated == res1.days_evaluated
    assert service.cache.get_stats().hits == 1

    # Cache invalidation clears it
    service.invalidate_cache()
    assert service.cache.get_stats().entries == 0
