"""Request ID and Structured Access Logging Middleware.

Guarantees request traceability via X-Request-ID across all endpoints.
Provides latency tracking and privacy-safe HTTP access logs.
"""

import logging
import re
import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.logging import request_id_ctx_var

logger = logging.getLogger("sangram_ai.access")

# Request ID sanitization pattern: alphanumeric with dashes and underscores, max 64 chars
REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# Interactive docs load Swagger UI / ReDoc assets and inline bootstrapping scripts.
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# JSON/SSE API responses never need to load subresources.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensures every incoming request has a valid Request ID for traceability."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming_req_id = request.headers.get("x-request-id")
        if incoming_req_id and REQUEST_ID_REGEX.match(incoming_req_id):
            request_id = incoming_req_id
        else:
            request_id = f"req_{uuid.uuid4().hex[:16]}"

        # Bind to contextvar for the duration of this request
        token = request_id_ctx_var.set(request_id)
        request.state.request_id = request_id

        try:
            response: Response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
        finally:
            request_id_ctx_var.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive HTTP response headers (Helmet-equivalent for the API)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )

        path = request.url.path
        is_docs = (
            path == "/openapi.json"
            or path == "/docs"
            or path.startswith("/docs/")
            or path == "/redoc"
            or path.startswith("/redoc/")
        )
        response.headers.setdefault("Content-Security-Policy", DOCS_CSP if is_docs else API_CSP)

        # HSTS is only meaningful (and safe) for production HTTPS deployments.
        if get_settings().ENVIRONMENT == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )

        return response


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests with timing and status code.

    NEVER logs request/response bodies, passwords, tokens, or cookies.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        req_id = getattr(request.state, "request_id", None) or request_id_ctx_var.get()

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Skip health check logging in quiet mode unless status >= 400 to avoid noisy logs
            is_health = request.url.path in ("/health", "/health/live", "/health/ready")
            if not is_health or response.status_code >= 400:
                logger.info(
                    f"{request.method} {request.url.path} returned {response.status_code} in {duration_ms}ms",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": request.client.host if request.client else "unknown",
                        "request_id": req_id,
                    },
                )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"{request.method} {request.url.path} failed with unhandled exception in {duration_ms}ms",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else "unknown",
                    "request_id": req_id,
                },
                exc_info=exc,
            )
            raise
