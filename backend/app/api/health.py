import logging
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """프로세스 liveness만 확인하며 외부 dependency를 조회하지 않습니다."""
    return {"status": "ok"}


@router.get("/ready")
def readiness_check(request: Request) -> dict[str, str]:
    """API 요청 처리에 필수인 PostgreSQL 연결 가능 여부를 확인합니다."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Readiness database check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    checks: list[Callable[[], bool]] = getattr(request.app.state, "readiness_checks", [])
    try:
        if not all(check() for check in checks):
            raise RuntimeError("dependency unavailable")
    except Exception as exc:
        logger.warning("Readiness dependency check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="dependency unavailable",
        ) from exc
    return {"status": "ready"}
