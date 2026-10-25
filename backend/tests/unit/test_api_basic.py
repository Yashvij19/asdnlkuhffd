"""
Unit tests for foundational API endpoints (/api/v1/health and /api/v1/meta).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Test health check returns HTTP 200 with healthy status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "Wind Generation Forecast Monitor" in data["app"]


def test_meta_endpoint() -> None:
    """Test metadata endpoint exposes configuration defaults and attribution."""
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_month_start"] == "2026-01-01"
    assert data["decision_month_end"] == "2026-01-31"
    assert data["default_cutoff"] == "09:00"
    assert data["timezone"] == "Europe/London"
    assert "Elexon Limited" in data["attribution"]


def test_discovery_contracts_endpoint() -> None:
    """Test discovery contracts endpoint returns verified Elexon parameter definitions and samples."""
    response = client.get("/api/v1/discovery/contracts")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "verified"
    assert "FUELHH" in data["datasets"]
    assert "WINDFOR" in data["datasets"]
    fuelhh = data["datasets"]["FUELHH"]
    assert fuelhh["fixture_record_count"] == 48
    assert fuelhh["parameters"]["fuel_type"] == "fuelType"
    assert fuelhh["sample"]["fuelType"] == "WIND"
    windfor = data["datasets"]["WINDFOR"]
    assert windfor["fixture_record_count"] > 0
    assert windfor["sample"]["dataset"] == "WINDFOR"


def test_storage_status_endpoint() -> None:
    """Test storage status endpoint returns database readiness and parser verification."""
    response = client.get("/api/v1/storage/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["backend"] == "sqlite"
    assert "actual_wind" in data["tables"]
    assert "wind_forecast" in data["tables"]
    assert "ingest_run" in data["tables"]
    assert data["parsers"]["FUELHH"]["status"] == "verified"
    assert data["parsers"]["WINDFOR"]["status"] == "verified"
    assert "actual_wind" in data["row_counts"]
    assert "wind_forecast" in data["row_counts"]


def test_day_ahead_endpoint_success() -> None:
    """Test day-ahead endpoint returns 48 points with coverage and summary."""
    response = client.get("/api/v1/day-ahead?decision_date=2026-01-01&cutoff=09:00")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_date"] == "2026-01-01"
    assert data["delivery_date"] == "2026-01-02"
    assert data["cutoff_local"] == "09:00"
    assert "coverage" in data
    assert data["coverage"]["periods"] == 48
    assert len(data["points"]) == 48

    first_point = data["points"][0]
    assert first_point["settlement_period"] == 1
    assert "actual_mw" in first_point
    assert "forecast_mw" in first_point


def test_day_ahead_endpoint_invalid_inputs() -> None:
    """Test validation errors for invalid date and cutoff parameters."""
    res_bad_date = client.get("/api/v1/day-ahead?decision_date=not-a-date")
    assert res_bad_date.status_code == 422

    res_bad_cutoff = client.get("/api/v1/day-ahead?cutoff=26:00")
    assert res_bad_cutoff.status_code == 400


def test_accuracy_summary_endpoint() -> None:
    """Test accuracy summary endpoint returns headline metrics and quantiles."""
    response = client.get("/api/v1/accuracy/summary?from=2026-01-01&to=2026-01-07&cutoff=09:00")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_from"] == "2026-01-01"
    assert data["decision_to"] == "2026-01-07"
    assert data["days_evaluated"] == 7
    assert "metrics" in data
    m = data["metrics"]
    assert m["evaluated_points"] == 7 * 24
    assert m["total_expected_periods"] == 7 * 48
    assert m["coverage_pct"] == 50.0
    assert m["mae_mw"] > 0
    assert m["rmse_mw"] >= m["mae_mw"]
    assert "quantiles" in m
    assert m["quantiles"]["p50"] is not None


def test_accuracy_distribution_endpoint() -> None:
    """Test error distribution endpoint returns histogram bins and sample stats."""
    response = client.get("/api/v1/accuracy/distribution?from=2026-01-01&to=2026-01-03&bins=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total_samples"] == 3 * 24
    assert len(data["bins"]) == 10
    assert data["min_error_mw"] <= data["max_error_mw"]
    assert "quantiles" in data


def test_accuracy_endpoint_date_validation() -> None:
    """Test 400 response when from_date is after to_date."""
    response = client.get("/api/v1/accuracy/summary?from=2026-01-10&to=2026-01-05")
    assert response.status_code == 400
    assert "from date cannot be after to date" in response.json()["detail"]


def test_accuracy_breakdowns_endpoints() -> None:
    """Test multi-dimensional breakdown API routes."""
    # 1. By Day
    res_day = client.get("/api/v1/accuracy/by-day?from=2026-01-01&to=2026-01-03")
    assert res_day.status_code == 200
    data_day = res_day.json()
    assert data_day["dimension"] == "day"
    assert len(data_day["items"]) == 3

    # 2. By Hour
    res_hour = client.get("/api/v1/accuracy/by-hour?from=2026-01-01&to=2026-01-03")
    assert res_hour.status_code == 200
    data_hour = res_hour.json()
    assert data_hour["dimension"] == "hour"
    assert len(data_hour["items"]) == 24

    # 3. By Horizon
    res_hor = client.get("/api/v1/accuracy/by-horizon?from=2026-01-01&to=2026-01-03")
    assert res_hor.status_code == 200
    assert res_hor.json()["dimension"] == "horizon"

    # 4. By Level
    res_lvl = client.get("/api/v1/accuracy/by-level?from=2026-01-01&to=2026-01-03")
    assert res_lvl.status_code == 200
    assert res_lvl.json()["dimension"] == "level"


def test_procurement_buffer_endpoint() -> None:
    """Test procurement safety buffer endpoint."""
    response = client.get("/api/v1/accuracy/buffer?from=2026-01-01&to=2026-01-05&confidence=0.90")
    assert response.status_code == 200
    data = response.json()
    assert data["confidence"] == 0.90
    assert data["confidence_pct"] == 90.0
    assert data["overall_buffer_mw"] >= 0.0
    assert len(data["hourly_buffers"]) == 24
    assert data["hourly_buffers"][0]["buffer_mw"] >= 0.0

    # Test confidence validation error (< 0.50)
    res_bad = client.get("/api/v1/accuracy/buffer?confidence=0.30")
    assert res_bad.status_code == 422

