"""
Unit & Integration Tests for Production Hardening (Phase 3.4).
Verifies:
- Request ID generation & propagation (X-Request-ID)
- Security headers (CSP, nosniff, DENY, etc.)
- /ready and /health operational endpoints
- RFC 7807 problem+json error formatting
- Metadata and attribution
"""

import uuid

from fastapi.testclient import TestClient

from app.main import create_app


def test_request_id_generated_when_missing() -> None:
    """Verify server generates UUID4 when X-Request-ID is not supplied by client."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        req_id = resp.headers.get("x-request-id")
        assert req_id is not None
        # Must be valid UUID4
        parsed = uuid.UUID(req_id, version=4)
        assert str(parsed) == req_id


def test_request_id_propagated_when_supplied() -> None:
    """Verify server preserves and echoes client-supplied X-Request-ID for distributed tracing."""
    app = create_app()
    with TestClient(app) as client:
        custom_id = "desk-trace-98765-xyz"
        resp = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200
        assert resp.headers.get("x-request-id") == custom_id


def test_security_headers_present() -> None:
    """Verify standard defense-in-depth HTTP security headers on all responses."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
        headers = resp.headers

        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in headers.get("permissions-policy", "")
        csp = headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp


def test_readiness_probe_success() -> None:
    """Verify /ready probe returns 200 with row counts and decision window when seeded."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["data_ready"] is True
        assert data["row_counts"]["actual_wind"] > 0
        assert data["row_counts"]["wind_forecast"] > 0
        assert data["decision_window"]["start"] == "2026-01-01"
        assert data["decision_window"]["end"] == "2026-01-31"

        # Verify /ready alias
        resp_alias = client.get("/ready")
        assert resp_alias.status_code == 200
        assert resp_alias.json()["status"] == "ready"


def test_rfc7807_problem_details_on_400_bad_request() -> None:
    """Verify 400 Bad Request outputs RFC 7807 application/problem+json."""
    app = create_app()
    with TestClient(app) as client:
        # from date after to date triggers HTTPException(400)
        resp = client.get("/api/v1/accuracy/summary?from=2026-01-20&to=2026-01-10")
        assert resp.status_code == 400
        assert "application/problem+json" in resp.headers["content-type"]
        assert resp.headers.get("x-request-id") is not None

        body = resp.json()
        assert body["type"] == "about:blank"
        assert body["title"] == "Bad Request"
        assert body["status"] == 400
        assert "from date cannot be after to date" in body["detail"]
        assert body["instance"] == "/api/v1/accuracy/summary"
        assert body["request_id"] == resp.headers["x-request-id"]


def test_rfc7807_problem_details_on_422_validation_error() -> None:
    """Verify 422 Unprocessable Entity outputs RFC 7807 application/problem+json."""
    app = create_app()
    with TestClient(app) as client:
        # Invalid cutoff regex pattern triggers RequestValidationError (422)
        resp = client.get("/api/v1/day-ahead?decision_date=2026-01-01&cutoff=invalid-cutoff")
        assert resp.status_code == 422
        assert "application/problem+json" in resp.headers["content-type"]
        assert resp.headers.get("x-request-id") is not None

        body = resp.json()
        assert body["type"] == "about:blank"
        assert body["title"] == "Unprocessable Entity"
        assert body["status"] == 422
        assert body["instance"] == "/api/v1/day-ahead"
        assert body["request_id"] == resp.headers["x-request-id"]


def test_rfc7807_problem_details_on_404_not_found() -> None:
    """Verify 404 Not Found outputs RFC 7807 application/problem+json."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/nonexistent-route-xyz")
        assert resp.status_code == 404
        assert "application/problem+json" in resp.headers["content-type"]
        body = resp.json()
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["request_id"] is not None


def test_meta_and_health_probes() -> None:
    """Verify health and metadata operational endpoints."""
    app = create_app()
    with TestClient(app) as client:
        # Health probe
        resp_health = client.get("/api/v1/health")
        assert resp_health.status_code == 200
        assert resp_health.json()["status"] == "healthy"

        # Health probe alias
        resp_health_alias = client.get("/health")
        assert resp_health_alias.status_code == 200
        assert resp_health_alias.json()["status"] == "healthy"

        # Metadata endpoint
        resp_meta = client.get("/api/v1/meta")
        assert resp_meta.status_code == 200
        meta = resp_meta.json()
        assert meta["version"] == "0.1.0"
        assert meta["decision_month_start"] == "2026-01-01"
        assert meta["decision_month_end"] == "2026-01-31"
        assert meta["default_cutoff"] == "09:00"
        assert "Elexon Limited" in meta["attribution"]
