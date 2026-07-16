from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TradeOut(BaseModel):
    """거래 내역 조회 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    action: str
    price: float | None
    volume: float | None
    status: str
    created_at: datetime
