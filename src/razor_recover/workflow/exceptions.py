"""Centralized exceptions for the recovery workflow (orchestration)."""

from __future__ import annotations


class WorkflowError(Exception):
    """Base exception for the recovery workflow."""


class TransactionNotFoundError(WorkflowError):
    """The requested transaction does not exist (-> HTTP 404)."""


class MerchantNotFoundError(WorkflowError):
    """The transaction's merchant could not be resolved."""


class WorkflowStageError(WorkflowError):
    """A pipeline stage failed in a controlled way; nothing was executed."""


class MLStageError(WorkflowStageError):
    """ML prediction stage failed."""


class LLMStageError(WorkflowStageError):
    """LLM decision stage failed."""


class PolicyStageError(WorkflowStageError):
    """Policy evaluation failed (fail closed)."""


__all__ = [
    "WorkflowError",
    "TransactionNotFoundError",
    "MerchantNotFoundError",
    "WorkflowStageError",
    "MLStageError",
    "LLMStageError",
    "PolicyStageError",
]
