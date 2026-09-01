from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.strategy import UserStrategy
from app.strategy.subscription_control import set_subscriptions_paused


router = APIRouter(prefix="/internal/strategy", tags=["Strategy Internal"])


class PauseSubscriptionsCommand(BaseModel):
    user_id: int
    subscription_ids: list[int]
    paused: bool


@router.post("/subscriptions/pause")
def pause_subscriptions(command: PauseSubscriptionsCommand, db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "updated": set_subscriptions_paused(
            db,
            user_id=command.user_id,
            subscription_ids=command.subscription_ids,
            paused=command.paused,
        )
    }


@router.post("/users/{user_id}/disable-live-subscriptions")
def disable_live_subscriptions(user_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    updated = (
        db.query(UserStrategy)
        .filter(UserStrategy.user_id == user_id, UserStrategy.mode == "live")
        .update({UserStrategy.enabled: False}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}
