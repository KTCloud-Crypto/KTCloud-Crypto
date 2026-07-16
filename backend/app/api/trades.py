from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.trade import Trade
from app.models.user import User
from app.schemas.trades import TradeOut

router = APIRouter(
    prefix="/trades",
    tags=["Trades"],
)


@router.get("", response_model=list[TradeOut])
def list_trades(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Trade]:
    """내 거래내역을 최근 200건까지 조회합니다."""
    return (
        db.query(Trade)
        .filter(Trade.user_id == current_user.id)
        .order_by(Trade.created_at.desc())
        .limit(200)
        .all()
    )
