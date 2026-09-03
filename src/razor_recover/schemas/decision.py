"""RecoveryDecision Pydantic schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RecoveryDecisionBase(BaseModel):
    transaction_id: int
    action: str
    outcome: str = "authorized"
    risk_score: Decimal | None = None
    policy_id: int | None = None
    policy_version: int | None = None
    rationale: str | None = None
    decided_at: datetime


class RecoveryDecisionCreate(RecoveryDecisionBase):
    pass


class RecoveryDecisionRead(RecoveryDecisionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
