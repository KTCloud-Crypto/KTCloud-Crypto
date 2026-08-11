from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings


request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)

_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|password|secret|token|api[_-]?key|access[_-]?key)", re.IGNORECASE
)
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")


def _sanitize(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _BEARER.sub("Bearer [REDACTED]", value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """Loki에서 파싱 가능한 한 줄 JSON 로그 포맷터입니다."""

    _standard = set(logging.LogRecord(None, 0, "", 0, "", (), None).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "log_type": getattr(record, "log_type", "operation"),
            "service": getattr(record, "service", "application"),
            "environment": settings.environment,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_var.get()
        user_id = getattr(record, "user_id", None) or user_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if user_id is not None:
            payload["user_id"] = user_id
        for key, value in record.__dict__.items():
            if key not in self._standard and key not in payload and key not in {"args", "msg"}:
                payload[key] = _sanitize(value, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_sanitize(payload), ensure_ascii=False, separators=(",", ":"))


def configure_logging(service: str) -> None:
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    if settings.is_production and level < logging.INFO and not settings.log_debug_enabled:
        level = logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(lambda record: setattr(record, "service", getattr(record, "service", service)) or True)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, level: int, event: str, *, log_type: str = "operation", **fields: Any) -> None:
    logger.log(level, event, extra={"event": event, "log_type": log_type, **fields})
