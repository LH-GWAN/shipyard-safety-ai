"""구조화 로깅과 요청 로깅 미들웨어."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("yardguard")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


def log_event(message: str, **context: Any) -> None:
    logger.info(message, extra={"context": context})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """request_id, endpoint, status_code, duration_ms를 구조화해 남긴다."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            "http_request",
            request_id=request_id,
            endpoint=f"{request.method} {request.url.path}",
            status_code=response.status_code,
            duration_ms=duration_ms,
            analysis_id=getattr(request.state, "analysis_id", None),
        )
        response.headers["x-request-id"] = request_id
        return response
