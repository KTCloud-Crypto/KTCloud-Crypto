from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.logging import log_event, request_id_var, user_id_var
from app.core.metrics import HTTP_DURATION, HTTP_IN_PROGRESS, HTTP_REQUESTS
from app.core.client_ip import resolve_client_ip


logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", "")[:128] or str(uuid.uuid4())
        request_token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)
        started = time.perf_counter()
        status_code = 500
        HTTP_IN_PROGRESS.inc()
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("Unhandled request error", extra={"event": "http_request_failed"})
            raise
        finally:
            if request.url.path not in {"/health", "/ready", "/metrics"}:
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                route = request.scope.get("route")
                route_path = getattr(route, "path", request.url.path)
                HTTP_REQUESTS.labels(request.method, route_path, str(status_code)).inc()
                HTTP_DURATION.labels(request.method, route_path).observe(duration_ms / 1000)
                log_event(
                    logger,
                    logging.ERROR if status_code >= 500 else logging.INFO,
                    "http_request_completed",
                    method=request.method,
                    path=request.url.path,
                    route=route_path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    client_ip=resolve_client_ip(request),
                )
            HTTP_IN_PROGRESS.dec()
            request_id_var.reset(request_token)
            user_id_var.reset(user_token)
