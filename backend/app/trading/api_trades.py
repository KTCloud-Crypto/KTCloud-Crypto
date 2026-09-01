from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.identity.dependencies import get_current_user
from app.core.database import get_db
from app.models.trade import Trade
from app.models.strategy import Strategy, UserStrategy
from app.models.strategy_signal import StrategyExecution
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
) -> list[TradeOut]:
    """내 거래내역을 최근 200건까지 조회합니다."""
    rows = (
        db.query(Trade, Strategy)
        .outerjoin(StrategyExecution, StrategyExecution.id == Trade.strategy_execution_id)
        .outerjoin(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
        .outerjoin(Strategy, Strategy.id == UserStrategy.strategy_id)
        .filter(Trade.user_id == current_user.id)
        .order_by(Trade.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        TradeOut(
            id=trade.id,
            strategy_execution_id=trade.strategy_execution_id,
            strategy_name=strategy.name if strategy else None,
            ticker=trade.ticker,
            action=trade.action,
            price=trade.price,
            volume=trade.volume,
            status=trade.status,
            created_at=trade.created_at,
        )
        for trade, strategy in rows
    ]
