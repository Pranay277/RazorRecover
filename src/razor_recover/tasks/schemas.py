"""Request/response schemas for the asynchronous recovery endpoints.

These shapes are deliberately stable and never carry secrets, internal stack
traces, or full PII - the same contract as the synchronous evaluation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskAccepted(BaseModel):
    """Immediate response when a recovery evaluation is queued for async run."""

    task_id: str
    status: str = "queued"
    transaction_id: int = Field(gt=0)


class TaskStatusResponse(BaseModel):
    """Stable view of one asynchronous recovery task.

    ``status`` is one of ``PENDING`` / ``STARTED`` / ``SUCCESS`` / ``FAILURE``.
    On success, ``result`` holds the serialized evaluation response; on failure,
    ``error`` holds a safe user-facing message (never a stack trace).
    """

    task_id: str
    transaction_id: int | None = None
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


__all__ = ["TaskAccepted", "TaskStatusResponse"]