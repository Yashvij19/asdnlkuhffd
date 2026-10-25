"""
Unit & Integration Tests for Naive 24h Persistence Benchmark & Skill Score Engine (FR-ACC-6, Phase 3.2).
"""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.benchmark import compute_persistence_benchmark
from app.main import create_app
from app.models import ActualWind, WindForecast
from app.schemas import PersistenceBenchmarkResult


def test_hand_computed_persistence_benchmark(memory_db_session: Session) -> None:
    """Verify mathematical calculation of MAE, RMSE, Bias, and Skill Score against hand checks."""
    # Jan 4: Day 0 (t - 24h for Jan 5 delivery)
    t0_1 = datetime(2026, 1, 4, 12, 0, tzinfo=UTC)
    t0_2 = datetime(2026, 1, 4, 13, 0, tzinfo=UTC)
    memory_db_session.add(
        ActualWind(
            start_time_utc=t0_1,
            settlement_date="2026-01-04",
            settlement_period=25,
            generation_mw=10000.0,
            source_publish_time_utc=t0_1,
        )
    )
    memory_db_session.add(
        ActualWind(
            start_time_utc=t0_2,
            settlement_date="2026-01-04",
            settlement_period=27,
            generation_mw=10500.0,
            source_publish_time_utc=t0_2,
        )
    )

    # Jan 5: Delivery day
    t1_1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    t1_2 = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)
    memory_db_session.add(
        ActualWind(
            start_time_utc=t1_1,
            settlement_date="2026-01-05",
            settlement_period=25,
            generation_mw=12000.0,
            source_publish_time_utc=t1_1,
        )
    )
    memory_db_session.add(
        ActualWind(
            start_time_utc=t1_2,
            settlement_date="2026-01-05",
            settlement_period=27,
            generation_mw=12500.0,
            source_publish_time_utc=t1_2,
        )
    )

    # Forecast published at D-1 08:30 (before 09:00 cut-off on Jan 4)
    pub_time = datetime(2026, 1, 4, 8, 30, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(
            start_time_utc=t1_1,
            publish_time_utc=pub_time,
            generation_mw=11000.0,
            horizon_hours=27.5,
        )
    )
    memory_db_session.add(
        WindForecast(
            start_time_utc=t1_2,
            publish_time_utc=pub_time,
            generation_mw=11700.0,
            horizon_hours=28.5,
        )
    )

    memory_db_session.commit()

    # Decision date: Jan 4 (Delivery date: Jan 5)
    res = compute_persistence_benchmark(
        session=memory_db_session,
        decision_from=date(2026, 1, 4),
        decision_to=date(2026, 1, 4),
        cutoff_str="09:00",
    )

    assert isinstance(res, PersistenceBenchmarkResult)
    assert res.total_samples == 2

    # Hand verification:
    # Period 25:
    #   Actual = 12000, Forecast = 11000, Persistence = 10000
    #   Forecast Error = 12000 - 11000 = +1000
    #   Persistence Error = 12000 - 10000 = +2000
    # Period 27:
    #   Actual = 12500, Forecast = 11700, Persistence = 10500
    #   Forecast Error = 12500 - 11700 = +800
    #   Persistence Error = 12500 - 10500 = +2000
    # Forecast MAE = (1000 + 800) / 2 = 900.0
    # Persistence MAE = (2000 + 2000) / 2 = 2000.0
    assert res.forecast_mae_mw == 900.0
    assert res.persistence_mae_mw == 2000.0

    # Skill Score = 1 - (900 / 2000) = 1 - 0.45 = 0.55 (55.0%)
    assert res.overall_skill_score == 0.55
    assert res.overall_skill_score_pct == 55.0
    assert res.days_forecast_won == 1
    assert res.days_persistence_won == 0


def test_benchmark_skill_score_properties(memory_db_session: Session) -> None:
    """Verify edge conditions for skill scores: perfect forecast, tied baseline, and worse forecast."""
    # Jan 10 prior actual
    t0 = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    memory_db_session.add(
        ActualWind(
            start_time_utc=t0,
            settlement_date="2026-01-10",
            settlement_period=25,
            generation_mw=10000.0,
            source_publish_time_utc=t0,
        )
    )

    # Jan 11 delivery actual
    t1 = datetime(2026, 1, 11, 12, 0, tzinfo=UTC)
    memory_db_session.add(
        ActualWind(
            start_time_utc=t1,
            settlement_date="2026-01-11",
            settlement_period=25,
            generation_mw=12000.0,
            source_publish_time_utc=t1,
        )
    )

    # Case A: Perfect forecast (error = 0) -> Skill Score == 1.0
    pub_time = datetime(2026, 1, 10, 8, 0, tzinfo=UTC)
    fc = WindForecast(
        start_time_utc=t1,
        publish_time_utc=pub_time,
        generation_mw=12000.0,
        horizon_hours=28.0,
    )
    memory_db_session.add(fc)
    memory_db_session.commit()

    res_perfect = compute_persistence_benchmark(
        session=memory_db_session,
        decision_from=date(2026, 1, 10),
        decision_to=date(2026, 1, 10),
    )
    assert res_perfect.forecast_mae_mw == 0.0
    assert res_perfect.overall_skill_score == 1.0
    assert res_perfect.overall_skill_score_pct == 100.0

    # Case B: Forecast identical to persistence (generation_mw = 10000.0) -> Skill Score == 0.0
    fc.generation_mw = 10000.0
    memory_db_session.commit()

    res_tied = compute_persistence_benchmark(
        session=memory_db_session,
        decision_from=date(2026, 1, 10),
        decision_to=date(2026, 1, 10),
    )
    assert res_tied.overall_skill_score == 0.0

    # Case C: Forecast worse than persistence (e.g. forecast = 16000 -> err = 4000 vs persistence err = 2000)
    fc.generation_mw = 16000.0
    memory_db_session.commit()

    res_worse = compute_persistence_benchmark(
        session=memory_db_session,
        decision_from=date(2026, 1, 10),
        decision_to=date(2026, 1, 10),
    )
    assert res_worse.overall_skill_score < 0.0
    assert res_worse.days_persistence_won == 1


def test_benchmark_endpoint_integration() -> None:
    """Test REST API endpoint GET /api/v1/accuracy/benchmark with seed database."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/accuracy/benchmark?from=2026-01-01&to=2026-01-31&cutoff=09:00")
        assert resp.status_code == 200
        data = resp.json()

        assert data["decision_from"] == "2026-01-01"
        assert data["decision_to"] == "2026-01-31"
        assert data["total_samples"] == 744
        assert data["forecast_mae_mw"] > 0.0
        assert data["persistence_mae_mw"] > 0.0
        # In reality, day-ahead meteorological forecast significantly outperforms naive 24h persistence
        assert data["overall_skill_score"] > 0.20  # Expect > 20% improvement over naive persistence
        assert data["days_forecast_won"] > data["days_persistence_won"]
        assert len(data["daily_comparison"]) >= 30

        # Test date range validation
        bad_resp = client.get("/api/v1/accuracy/benchmark?from=2026-01-20&to=2026-01-10")
        assert bad_resp.status_code == 400
