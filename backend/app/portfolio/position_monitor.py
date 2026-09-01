"""실제 Upbit 잔고와 실전 전략 기록의 불일치를 주기적으로 감시합니다."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.api_key import ApiKey
from app.models.position_mismatch import PositionMismatchIncident
from app.models.strategy import UserStrategy
from app.models.user import User
from app.identity import resolve_exchange_credentials
from app.portfolio.position_reconciliation import actual_coin_totals, recorded_strategy_volumes, reconciliation_status
from app.messaging.notification_events import enqueue_notification_requested
from app.market_data import get_accounts
from app.core.metrics import POSITION_MISMATCHES

logger = logging.getLogger(__name__)


def mismatch_notification_text(
    currency: str,
    actual_total: float,
    strategy_volume: float,
    difference: float,
) -> str:
    """사용자가 차이와 필요한 조치를 바로 이해할 수 있는 알림을 만듭니다."""
    cause = "전략 기록보다 실제 Upbit 잔고가 부족합니다."
    heading = "⚠️ [실전 포지션 조정 필요]"
    return "\n".join([
        heading,
        f"🪙 화폐: {currency}",
        f"🏦 Upbit 총보유량: {actual_total:.8f}",
        f"📊 전략 기록 수량: {strategy_volume:.8f}",
        f"⚖️ 차이: {difference:+.8f}",
        f"📌 {cause}",
        "🔄 웹의 실전계좌 화면에서 확인해 주세요.",
        "ℹ️ 자동으로 특정 전략에서 차감하지는 않습니다.",
    ])


def _active_incidents(db: Session, user_id: int, currency: str) -> list[PositionMismatchIncident]:
    return (
        db.query(PositionMismatchIncident)
        .filter(
            PositionMismatchIncident.user_id == user_id,
            PositionMismatchIncident.currency == currency,
            PositionMismatchIncident.resolved_at.is_(None),
        )
        .all()
    )


def _record_currency_state(
    db: Session,
    user: User,
    currency: str,
    actual_total: float,
    strategy_volume: float,
    now: datetime,
) -> int:
    """한 화폐의 사건 상태를 갱신하고 새 Telegram 알림 수를 반환합니다."""
    mismatch_type, _ = reconciliation_status(actual_total, strategy_volume)
    active = _active_incidents(db, user.id, currency)
    # positive discrepancy는 정상적인 read-only 미배정 상태이므로 incident나
    # 사용자 조치 알림을 만들지 않습니다.
    if mismatch_type in {"matched", "external_balance"}:
        for incident in active:
            incident.resolved_at = now
            incident.last_seen_at = now
        return 0

    for incident in active:
        if incident.mismatch_type != mismatch_type:
            incident.resolved_at = now
            incident.last_seen_at = now

    incident = next((item for item in active if item.mismatch_type == mismatch_type), None)
    difference = actual_total - strategy_volume
    if incident is None:
        incident = PositionMismatchIncident(
            user_id=user.id,
            currency=currency,
            mismatch_type=mismatch_type,
            actual_total=actual_total,
            strategy_volume=strategy_volume,
            difference=difference,
            detected_at=now,
            last_seen_at=now,
        )
        db.add(incident)
        db.flush()
        POSITION_MISMATCHES.labels(f"KRW-{currency}").inc()
    else:
        incident.actual_total = actual_total
        incident.strategy_volume = strategy_volume
        incident.difference = difference
        incident.last_seen_at = now

    if incident.notified_at is not None or not user.telegram_chat_id:
        return 0
    queued = enqueue_notification_requested(
        db,
        chat_id=user.telegram_chat_id,
        message=mismatch_notification_text(currency, actual_total, strategy_volume, difference),
        producer="portfolio-worker",
        notification_type="position_mismatch",
        user_id=user.id,
        idempotency_key=f"position-mismatch:{incident.id}",
    )
    if queued:
        incident.notified_at = now
        return 1
    return 0


def monitor_position_mismatches() -> tuple[int, int]:
    """실전 전략 사용자의 잔고를 한 번 검사하고 (검사 사용자, 발송 알림)을 반환합니다."""
    db = SessionLocal()
    checked = 0
    notifications = 0
    try:
        users = (
            db.query(User)
            .join(ApiKey, ApiKey.user_id == User.id)
            .join(UserStrategy, UserStrategy.user_id == User.id)
            .filter(UserStrategy.mode == "live")
            .distinct()
            .all()
        )
        for user in users:
            try:
                api_key = db.query(ApiKey).filter(ApiKey.user_id == user.id).one()
                access_key, secret_key = resolve_exchange_credentials(api_key)
                accounts = get_accounts(
                    access_key=access_key,
                    secret_key=secret_key,
                    base_url=settings.upbit_api_base_url,
                )
                actual = actual_coin_totals(accounts)
                recorded = recorded_strategy_volumes(db, user.id)
                now = datetime.utcnow()
                for currency in sorted(set(actual) | set(recorded)):
                    notifications += _record_currency_state(
                        db,
                        user,
                        currency,
                        actual.get(currency, 0.0),
                        recorded.get(currency, 0.0),
                        now,
                    )
                db.commit()
                checked += 1
            except Exception as error:
                db.rollback()
                logger.warning(
                    "Position mismatch check failed: user_id=%s error=%s",
                    user.id,
                    type(error).__name__,
                )
        return checked, notifications
    finally:
        db.close()
