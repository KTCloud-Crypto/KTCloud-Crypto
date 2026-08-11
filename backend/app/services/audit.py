from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.logging import log_event, request_id_var
from app.core.metrics import SECURITY_EVENTS
from app.core.client_ip import resolve_client_ip
from app.models.security_audit_log import SecurityAuditLog


logger = logging.getLogger(__name__)


def record_security_event(
    db: Session,
    event_type: str,
    outcome: str,
    *,
    actor_user_id: int | None = None,
    actor_key: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
    commit: bool = True,
) -> SecurityAuditLog:
    entry = SecurityAuditLog(
        event_type=event_type,
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_key=actor_key,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id_var.get(),
        client_ip=resolve_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent", "")[:512] if request else None,
        detail=detail,
        metadata_json=metadata or {},
    )
    db.add(entry)
    if commit:
        db.commit()
    else:
        db.flush()
    log_event(
        logger,
        logging.WARNING if outcome == "failure" else logging.INFO,
        event_type,
        log_type="security",
        outcome=outcome,
        actor_user_id=actor_user_id,
        actor_key=actor_key,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        metadata=metadata or {},
    )
    SECURITY_EVENTS.labels(event_type, outcome).inc()
    return entry
