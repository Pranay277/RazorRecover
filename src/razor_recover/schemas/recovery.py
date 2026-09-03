"""RecoveryAttempt Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecoveryAttemptBase(BaseModel):
    transaction_id: int
    decision_id: int | None = None
    status: str = "pending"
    attempt_type: str
    error_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RecoveryAttemptCreate(RecoveryAttemptBase):
    pass


class RecoveryAttemptRead(RecoveryAttemptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
