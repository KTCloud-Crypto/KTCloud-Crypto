from datetime import datetime
 
from pydantic import BaseModel, ConfigDict, Field
 
 
class PaperAccountAdjustmentIn(BaseModel):
    target_net_deposit: float = Field(ge=0, le=10_000_000_000)
 
 
class PaperAccountCashIn(BaseModel):
    amount: float = Field(gt=0, le=10_000_000_000)
 
 
class PaperAccountOut(BaseModel):
    cash_balance: float
    # 활성 전략이 다음 매수에 쓰려고 확보한 금액입니다.
    reserved_amount: float = 0
    # 확보된 예산을 뺀, 새 전략에 배정할 수 있는 현금입니다.
    available_for_order: float = 0
    net_deposit: float
    holdings_value: float
    total_equity: float
    profit_loss: float
    return_rate: float | None
 
 
class PaperLedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    amount: float
    balance_after: float
    created_at: datetime
    realized_profit_loss: float | None = None