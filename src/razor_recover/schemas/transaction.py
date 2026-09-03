"""Transaction Pydantic schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TransactionBase(BaseModel):
    external_id: str
    customer_id: int
    merchant_id: int
    amount: Decimal
    currency: str = "USD"
    status: str = "failed"
    failure_code: str | None = None
    failure_reason: str | None = None
    attempted_at: datetime | None = None


class TransactionCreate(TransactionBase):
    pass


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
