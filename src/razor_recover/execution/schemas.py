"""Typed contracts for the execution layer.

Execution consumes an authorized ``PolicyDecision`` and returns structured
results so downstream (persistence, audit, API) never depends on gateway/HTTP
details.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GatewayOutcome(str, Enum):
    """Outcome of a simulated payment-gateway operation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class NotificationStatus(str, Enum):
    """Outcome of a notification delivery."""

    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExecutionStatus(str, Enum):
    """Canonical status of a recorded recovery attempt.

    Mirrors the strings stored on ``RecoveryAttempt.status``:
      recovered / failed / scheduled / sent / timeout
    """

    RECOVERED = "recovered"
    FAILED = "failed"
    SCHEDULED = "scheduled"
    SENT = "sent"
    TIMEOUT = "timeout"


class GatewayChargeResult(BaseModel):
    """Result returned by a payment gateway call."""

    outcome: GatewayOutcome
    reference: str
    message: str = ""
    error_code: str | None = None


class NotificationResult(BaseModel):
    """Result of a notification delivery attempt."""

    status: NotificationStatus
    channel: str = "email"
    message: str = ""


class ExecutionResult(BaseModel):
    """Final outcome of executing a single authorized action."""

    action: str
    status: ExecutionStatus
    attempt_id: int | None = None
    message: str = ""
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


__all__ = [
    "GatewayOutcome",
    "NotificationStatus",
    "ExecutionStatus",
    "GatewayChargeResult",
    "NotificationResult",
    "ExecutionResult",
]
