from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PositionOut(BaseModel):
    """DB에 기록된 포지션 조회 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    status: str | None
    updated_at: datetime


class UpbitBalanceOut(BaseModel):
    """업비트 실계좌 잔고 응답 스키마"""

    currency: str
    balance: float
    locked: float
    avg_buy_price: float
