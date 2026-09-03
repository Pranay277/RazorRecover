"""Merchant Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MerchantBase(BaseModel):
    external_id: str
    name: str
    industry: str | None = None
    status: str = "active"


class MerchantCreate(MerchantBase):
    pass


class MerchantRead(MerchantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
