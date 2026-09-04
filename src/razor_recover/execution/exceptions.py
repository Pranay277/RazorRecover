"""Centralized exceptions for the execution layer.

The execution layer PERFORMS authorized recovery actions. It never decides what
is safe - it only acts on an explicit ALLOW from the policy engine. Exceptions
here represent execution-time problems, not authorization decisions.
"""

from __future__ import annotations


class ExecutionError(Exception):
    """Base exception for the execution layer."""


class UnauthorizedExecutionError(ExecutionError):
    """Raised when something tries to execute without an ALLOW policy decision.

    This is the execution layer's independent safety guard: only
    ``PolicyDecision.final_action`` under an ALLOW decision may be executed.
    """


class GatewayError(ExecutionError):
    """Base exception for payment gateway failures."""


class GatewayUnavailableError(GatewayError):
    """The payment gateway could not be reached."""


class GatewayTimeoutError(GatewayError):
    """The payment gateway call exceeded its deadline."""


class NotificationError(ExecutionError):
    """Base exception for notification delivery failures."""


__all__ = [
    "ExecutionError",
    "UnauthorizedExecutionError",
    "GatewayError",
    "GatewayUnavailableError",
    "GatewayTimeoutError",
    "NotificationError",
]
