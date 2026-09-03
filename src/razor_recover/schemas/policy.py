"""Policy Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PolicyBase(BaseModel):
    name: str
    description: str | None = None
    expression: str
    enabled: bool = True
    priority: int = 100


class PolicyCreate(PolicyBase):
    pass


class PolicyRead(PolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
