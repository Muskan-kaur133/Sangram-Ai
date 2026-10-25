"""Liveness and Readiness Probes.

GET /health:       Convenience alias for the liveness probe.
GET /health/live:  Application process is running and responding to HTTP requests.
                   Independent of database or downstream network health.
GET /health/ready: Bounded check of PostgreSQL database connectivity.
                   Returns 200 OK when connected; returns 503 SERVICE_UNAVAILABLE when down.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, status

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.db.session import check_database_health
from app.schemas.common import HealthLiveResponse, HealthReadyResponse

router = APIRouter(prefix="/health", tags=["Health Probes"])


@router.get(
    "/live",
    response_model=HealthLiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Liveness Probe",
    description="Returns 200 OK if the ASGI process is running. Independent of database state.",
)
async def health_live() -> HealthLiveResponse:
    """Liveness probe for orchestrators and container healthchecks."""
    settings = get_settings()
    return HealthLiveResponse(
        status="ok",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "",
    response_model=HealthLiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Convenience alias for the liveness probe. Independent of database state.",
)
async def health_check() -> HealthLiveResponse:
    """Primary health endpoint used by load balancers and smoke tests."""
    return await health_live()


@router.get(
    "/ready",
    response_model=HealthReadyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        503: {
            "model": HealthReadyResponse,
            "description": "Database or critical backend dependency is unavailable.",
        }
    },
    summary="Database & Backend Readiness Probe",
    description="Executes a bounded SELECT 1 ping against PostgreSQL. Returns 503 if unreachable.",
)
async def health_ready() -> HealthReadyResponse:
    """Readiness probe ensuring database connection pool is operational."""
    is_healthy, duration_ms, error_msg = await check_database_health()

    if not is_healthy:
        raise ServiceUnavailableError(
            message=f"Readiness probe failed: Database connectivity unavailable. {error_msg or ''}".strip(),
            details={"database": "unavailable", "duration_ms": duration_ms},
        )

    return HealthReadyResponse(
        status="ok",
        database="connected",
        timestamp=datetime.now(timezone.utc),
        response_time_ms=duration_ms,
    )
