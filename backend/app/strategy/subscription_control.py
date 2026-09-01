from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.strategy import UserStrategy


def set_subscriptions_paused(
    db: Session,
    *,
    user_id: int,
    subscription_ids: Iterable[int],
    paused: bool,
) -> int:
    """사용자가 소유한 전략 구독의 신규 진입 일시정지 상태를 변경합니다."""
    target_ids = tuple(dict.fromkeys(subscription_ids))
    if not target_ids:
        return 0

    subscriptions = (
        db.query(UserStrategy)
        .filter(
            UserStrategy.user_id == user_id,
            UserStrategy.id.in_(target_ids),
        )
        .all()
    )
    for subscription in subscriptions:
        subscription.paused = paused
    db.commit()
    return len(subscriptions)
