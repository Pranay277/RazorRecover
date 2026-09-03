"""Customer Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerBase(BaseModel):
    external_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    status: str = "active"


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
