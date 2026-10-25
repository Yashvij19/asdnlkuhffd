"""
Production FastAPI Middleware and RFC 7807 Error Handlers (Phase 3.4).
Provides:
- Request ID correlation & propagation (X-Request-ID)
- Structured JSON access logging with duration_ms
- Defense-in-depth security headers (CSP, nosniff, DENY, etc.)
- RFC 7807 problem+json error formatting
- slowapi rate limiting integration
"""

import time
import uuid

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings
from app.logging import get_logger

logger = get_logger("app.middleware")

# Global Limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[get_settings().rate_limit],
)


class ProblemDetails(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs (application/problem+json)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    request_id: str | None = None


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every HTTP request has a unique request ID (UUID4).
    Propagates request ID through logging context and the X-Request-ID response header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        request_id = incoming_id if incoming_id else str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class StructuredAccessLoggingMiddleware(BaseHTTPMiddleware):
    """
    Emits structured access logs for every request with method, path, status,
    latency duration_ms, client IP, and request ID.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        client_host = request.client.host if request.client else "unknown"
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            req_id = getattr(request.state, "request_id", "unknown")

            logger.info(
                "http_request",
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_host,
                request_id=req_id,
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            req_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "http_request_failed",
                method=request.method,
                path=path,
                duration_ms=duration_ms,
                client_ip=client_host,
                request_id=req_id,
                error=str(exc),
            )
            raise exc


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies defense-in-depth HTTP security response headers.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        headers = response.headers

        # Prevent MIME-sniffing
        headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking defense
        headers["X-Frame-Options"] = "DENY"

        # Referrer privacy
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser capabilities
        headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # Content Security Policy (allows self, unsafe-inline styles/scripts for demo dashboard)
        headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*"
        )

        return response


# ==============================================================================
# RFC 7807 Exception Handlers
# ==============================================================================


def get_request_id(request: Request) -> str:
    """Safely extract request ID from request state or headers."""
    return getattr(request.state, "request_id", request.headers.get("x-request-id", "unknown"))


async def http_exception_handler(
    request: Request, exc: HTTPException | StarletteHTTPException
) -> JSONResponse:
    """Format HTTPExceptions according to RFC 7807 (application/problem+json)."""
    req_id = get_request_id(request)
    title_map = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }
    title = title_map.get(exc.status_code, "HTTP Error")
    detail = str(exc.detail) if hasattr(exc, "detail") else "An error occurred."

    problem = ProblemDetails(
        type="about:blank",
        title=title,
        status=exc.status_code,
        detail=detail,
        instance=request.url.path,
        request_id=req_id,
    )

    headers = {"X-Request-ID": req_id}
    if hasattr(exc, "headers") and exc.headers:
        headers.update(exc.headers)

    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
        headers=headers,
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """RFC 7807 formatting for 429 Too Many Requests."""
    req_id = get_request_id(request)
    problem = ProblemDetails(
        type="about:blank",
        title="Too Many Requests",
        status=429,
        detail=f"Rate limit exceeded: {exc.detail}",
        instance=request.url.path,
        request_id=req_id,
    )
    return JSONResponse(
        status_code=429,
        content=problem.model_dump(),
        media_type="application/problem+json",
        headers={"X-Request-ID": req_id, "Retry-After": "60"},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format RequestValidationErrors (422) according to RFC 7807."""
    req_id = get_request_id(request)
    errors = exc.errors()
    err_msgs: list[str] = []
    for err in errors:
        loc_str = ".".join(str(loc) for loc in err.get("loc", []))
        err_msgs.append(f"{loc_str}: {err.get('msg', 'invalid')}")
    detail = "; ".join(err_msgs) if err_msgs else "Validation error in request parameters"

    problem = ProblemDetails(
        type="about:blank",
        title="Unprocessable Entity",
        status=422,
        detail=detail,
        instance=request.url.path,
        request_id=req_id,
    )
    return JSONResponse(
        status_code=422,
        content=problem.model_dump(),
        media_type="application/problem+json",
        headers={"X-Request-ID": req_id},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Sanitized RFC 7807 500 handler to prevent leaking stack traces."""
    req_id = get_request_id(request)
    logger.error("unhandled_server_exception", error=str(exc), exc_info=True, request_id=req_id)

    problem = ProblemDetails(
        type="about:blank",
        title="Internal Server Error",
        status=500,
        detail="An internal server error occurred. Please reference the request ID when contacting support.",
        instance=request.url.path,
        request_id=req_id,
    )
    return JSONResponse(
        status_code=500,
        content=problem.model_dump(),
        media_type="application/problem+json",
        headers={"X-Request-ID": req_id},
    )


def register_middleware_and_handlers(app: FastAPI) -> None:
    """Register all production middleware, rate limiting, and RFC 7807 handlers."""
    # 1. State & rate limiting
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # 2. Security headers (outermost response modification)
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Access logging
    app.add_middleware(StructuredAccessLoggingMiddleware)

    # 4. Request ID propagation
    app.add_middleware(RequestIDMiddleware)

    # 5. RFC 7807 exception handlers
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
