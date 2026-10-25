"""
Integration tests for Analytics Engine and Caching Service over full January 2026 dataset.
Verifies complete month consistency, all-vintages horizon degradation curve,
and performance latency requirements (p95 < 300ms).
"""

import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_full_month_analytics_end_to_end() -> None:
    app = create_app()
    with TestClient(app) as client:
        # 1. Verify Storage Status and Seed Counts
        resp_storage = client.get("/api/v1/storage/status")
        assert resp_storage.status_code == 200
        storage_data = resp_storage.json()
        assert storage_data["status"] == "ready"
        assert storage_data["row_counts"]["actual_wind"] == 1536  # 32 delivery days (Jan 1 to Feb 1) * 48
        assert storage_data["row_counts"]["wind_forecast"] >= 19000

        # 2. Test Precomputed/Cached Headline Accuracy Summary (p95 < 300ms per spec)
        t0 = time.perf_counter()
        resp_summary = client.get("/api/v1/accuracy/summary?from=2026-01-01&to=2026-01-31&cutoff=09:00")
        dur_summary = (time.perf_counter() - t0) * 1000.0
        assert resp_summary.status_code == 200
        assert dur_summary < 300.0  # Precomputed/cached latency requirement < 300ms

        summary_data = resp_summary.json()
        assert summary_data["days_evaluated"] == 31
        metrics = summary_data["metrics"]
        assert metrics["evaluated_points"] == 744  # 31 * 24 hourly periods
        assert metrics["shortfall_frequency_pct"] > 70.0  # Systemic shortfall pattern
        assert metrics["bias_mw"] < 0  # Over-forecast / negative error

        # 3. Test Cache Invalidation and Refresh
        resp_inv = client.post("/api/v1/analytics/cache/invalidate")
        assert resp_inv.status_code == 200

        # Query after invalidation
        resp_after_inv = client.get("/api/v1/accuracy/summary?from=2026-01-01&to=2026-01-31&cutoff=09:00")
        assert resp_after_inv.status_code == 200

        # Test Cache Hit on second call (< 50ms)
        t0_cached = time.perf_counter()
        resp_cached = client.get("/api/v1/accuracy/summary?from=2026-01-01&to=2026-01-31&cutoff=09:00")
        dur_cached = (time.perf_counter() - t0_cached) * 1000.0
        assert resp_cached.status_code == 200
        assert dur_cached < 50.0  # Cached response is near-instant

        # 4. Test Error Distribution & Quantiles
        resp_dist = client.get("/api/v1/accuracy/distribution?from=2026-01-01&to=2026-01-31&bins=20")
        assert resp_dist.status_code == 200
        dist_data = resp_dist.json()
        assert dist_data["total_samples"] == 744
        assert len(dist_data["bins"]) == 20
        assert dist_data["quantiles"]["p5"] <= dist_data["quantiles"]["p50"] <= dist_data["quantiles"]["p95"]

        # 5. Test Multi-Dimensional Breakdowns
        # By Day (31 items)
        resp_day = client.get("/api/v1/accuracy/by-day?from=2026-01-01&to=2026-01-31")
        assert resp_day.status_code == 200
        day_data = resp_day.json()
        assert day_data["dimension"] == "day"
        assert len(day_data["items"]) == 31

        # By Hour (24 items: 0..23)
        resp_hour = client.get("/api/v1/accuracy/by-hour?from=2026-01-01&to=2026-01-31")
        assert resp_hour.status_code == 200
        hour_data = resp_hour.json()
        assert hour_data["dimension"] == "hour"
        assert len(hour_data["items"]) == 24

        # By Horizon
        resp_horiz = client.get("/api/v1/accuracy/by-horizon?from=2026-01-01&to=2026-01-31")
        assert resp_horiz.status_code == 200
        assert resp_horiz.json()["dimension"] == "horizon"

        # By Level (4 tiers)
        resp_level = client.get("/api/v1/accuracy/by-level?from=2026-01-01&to=2026-01-31")
        assert resp_level.status_code == 200
        assert resp_level.json()["dimension"] == "level"
        assert len(resp_level.json()["items"]) == 4

        # 6. Test Procurement Safety Buffer (FR-ACC-4)
        resp_buf = client.get("/api/v1/accuracy/buffer?from=2026-01-01&to=2026-01-31&confidence=0.90")
        assert resp_buf.status_code == 200
        buf_data = resp_buf.json()
        assert buf_data["total_samples"] == 744
        assert buf_data["confidence_pct"] == 90.0
        assert buf_data["overall_buffer_mw"] > 3000.0  # e.g. ~4154 MW safety margin
        assert len(buf_data["hourly_buffers"]) == 24

        # 7. Test All-Vintages Horizon Curve (FR-ACC-5)
        resp_curve = client.get("/api/v1/accuracy/horizon-curve?from=2026-01-01&to=2026-01-31&step=6")
        assert resp_curve.status_code == 200
        curve_data = resp_curve.json()
        assert curve_data["total_samples"] > 10000  # Evaluates over 11k vintage forecasts
        assert len(curve_data["curve"]) == 8  # 48 / 6 = 8 buckets
        # Verify forecast degradation property: MAE at 42-48h > MAE at 0-6h
        mae_near = curve_data["curve"][0]["mae_mw"]
        mae_far = curve_data["curve"][-1]["mae_mw"]
        assert mae_far > mae_near

        # 8. Verify Cache Diagnostics Endpoint
        resp_stats = client.get("/api/v1/analytics/cache/stats")
        assert resp_stats.status_code == 200
        stats_data = resp_stats.json()
        assert stats_data["entries"] > 0
        assert stats_data["hits"] >= 1
