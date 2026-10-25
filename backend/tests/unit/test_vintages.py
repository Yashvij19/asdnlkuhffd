"""
Unit tests for Multi-Vintage Evolution Analytics Engine (Phase 3.1).
"""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.vintages import get_day_ahead_vintages
from app.main import create_app
from app.models import ActualWind, WindForecast
from app.schemas import DayAheadVintagesResult


def test_day_ahead_vintages_grouping_and_ordering(memory_db_session: Session) -> None:
    # Delivery day: 2026-01-05
    d_date = date(2026, 1, 5)
    t1 = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 5, 13, 0, tzinfo=UTC)

    # Actuals
    memory_db_session.add(
        ActualWind(
            start_time_utc=t1,
            settlement_date=d_date,
            settlement_period=25,
            generation_mw=12000.0,
            source_publish_time_utc=t1,
        )
    )
    memory_db_session.add(
        ActualWind(
            start_time_utc=t2,
            settlement_date=d_date,
            settlement_period=27,
            generation_mw=12500.0,
            source_publish_time_utc=t2,
        )
    )

    # 3 distinct vintages published at different times
    # Vintage 1: D-2 (Jan 3 12:00)
    p1 = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(start_time_utc=t1, publish_time_utc=p1, generation_mw=10000.0, horizon_hours=48.0)
    )
    memory_db_session.add(
        WindForecast(start_time_utc=t2, publish_time_utc=p1, generation_mw=10500.0, horizon_hours=49.0)
    )

    # Vintage 2: D-1 09:00 Cutoff (Jan 4 09:00)
    p2 = datetime(2026, 1, 4, 9, 0, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(start_time_utc=t1, publish_time_utc=p2, generation_mw=11000.0, horizon_hours=27.0)
    )
    memory_db_session.add(
        WindForecast(start_time_utc=t2, publish_time_utc=p2, generation_mw=11800.0, horizon_hours=28.0)
    )

    # Vintage 3: Prompt Intraday (Jan 5 08:00)
    p3 = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
    memory_db_session.add(
        WindForecast(start_time_utc=t1, publish_time_utc=p3, generation_mw=11900.0, horizon_hours=4.0)
    )
    memory_db_session.add(
        WindForecast(start_time_utc=t2, publish_time_utc=p3, generation_mw=12400.0, horizon_hours=5.0)
    )

    memory_db_session.commit()

    res = get_day_ahead_vintages(memory_db_session, d_date)

    assert isinstance(res, DayAheadVintagesResult)
    assert res.delivery_date == "2026-01-05"
    assert res.total_vintages_available == 3
    assert res.returned_vintages == 3

    # Chronological ordering check
    assert res.vintages[0].publish_time_utc == p1
    assert res.vintages[1].publish_time_utc == p2
    assert res.vintages[2].publish_time_utc == p3

    # Error and MAE verification
    # For Vintage 1: errors are (12000 - 10000 = +2000), (12500 - 10500 = +2000) -> MAE=2000, Bias=2000
    assert res.vintages[0].mae_mw == 2000.0
    assert res.vintages[0].bias_mw == 2000.0

    # For Vintage 3 (Intraday): errors are (12000 - 11900 = +100), (12500 - 12400 = +100) -> MAE=100
    assert res.vintages[2].mae_mw == 100.0
    assert res.vintages[2].bias_mw == 100.0


def test_day_ahead_vintages_sampling_limit(memory_db_session: Session) -> None:
    d_date = date(2026, 1, 6)
    t = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)

    # Add 5 vintages
    for hour in [1, 2, 3, 4, 5]:
        p = datetime(2026, 1, 4, hour, 0, tzinfo=UTC)
        memory_db_session.add(
            WindForecast(start_time_utc=t, publish_time_utc=p, generation_mw=5000.0 + hour * 100, horizon_hours=50.0 - hour)
        )
    memory_db_session.commit()

    # Request limit of 3
    res = get_day_ahead_vintages(memory_db_session, d_date, limit_vintages=3)
    assert res.total_vintages_available == 5
    assert res.returned_vintages == 3
    # Check monotonic chronological order
    times = [v.publish_time_utc for v in res.vintages]
    assert times == sorted(times)


def test_vintages_endpoint_integration() -> None:
    app = create_app()
    with TestClient(app) as client:
        # 1. Valid query for January 15, 2026
        resp = client.get("/api/v1/day-ahead/vintages?delivery_date=2026-01-15")
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_date"] == "2026-01-15"
        assert data["total_vintages_available"] >= 20
        assert len(data["actuals"]) == 48
        assert len(data["vintages"]) > 0

        # 2. Limit vintages
        resp_lim = client.get("/api/v1/day-ahead/vintages?delivery_date=2026-01-15&limit_vintages=5")
        assert resp_lim.status_code == 200
        data_lim = resp_lim.json()
        assert data_lim["returned_vintages"] == 5

        # 3. Bad date validation
        resp_bad = client.get("/api/v1/day-ahead/vintages?delivery_date=invalid-date")
        assert resp_bad.status_code == 422 or resp_bad.status_code == 400
