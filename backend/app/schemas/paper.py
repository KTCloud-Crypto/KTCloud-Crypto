from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaperAccountAdjustmentIn(BaseModel):
    target_net_deposit: float = Field(ge=0, le=10_000_000_000)


class PaperAccountCashIn(BaseModel):
    amount: float = Field(gt=0, le=10_000_000_000)


class PaperAccountOut(BaseModel):
    cash_balance: float
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
