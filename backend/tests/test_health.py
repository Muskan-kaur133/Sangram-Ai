"""Tests for Health Probes and Security Headers.

Verifies:
1. /health and /health/live return 200 independent of database status.
2. /health/ready returns 200 when database connectivity succeeds.
3. /health/ready returns 503 SERVICE_UNAVAILABLE when database is down.
4. Baseline security headers are applied to responses.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe_returns_200(async_client: AsyncClient):
    """Liveness probe must return 200 OK with version and timestamp."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    assert response.headers.get("x-request-id") is not None


@pytest.mark.asyncio
async def test_health_alias_returns_200(async_client: AsyncClient):
    """GET /health is a stable convenience alias for the liveness probe."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    assert response.headers.get("x-request-id") is not None


@pytest.mark.asyncio
async def test_security_headers_are_present(async_client: AsyncClient):
    """Responses include baseline defensive headers without production-only HSTS."""
    response = await async_client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
async def test_docs_csp_allows_swagger_assets(async_client: AsyncClient):
    """CSP for the interactive docs must allow the CDN assets Swagger UI needs."""
    response = await async_client.get("/docs")

    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_readiness_probe_healthy(async_client: AsyncClient, monkeypatch):
    """Readiness probe returns 200 when controlled database check succeeds."""

    async def mock_check_db_healthy():
        return True, 1.25, None

    monkeypatch.setattr("app.api.v1.health.check_database_health", mock_check_db_healthy)

    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["response_time_ms"] == 1.25


@pytest.mark.asyncio
async def test_readiness_probe_unhealthy_returns_503(async_client: AsyncClient, monkeypatch):
    """Readiness probe returns 503 SERVICE_UNAVAILABLE when database is unreachable."""

    async def mock_check_db_unhealthy():
        return False, 2000.0, "Connection timeout to PostgreSQL"

    monkeypatch.setattr("app.api.v1.health.check_database_health", mock_check_db_unhealthy)

    response = await async_client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["code"] == "SERVICE_UNAVAILABLE"
    assert data["retryable"] is True
    assert "Database connectivity unavailable" in data["message"]
    assert data["details"]["database"] == "unavailable"
