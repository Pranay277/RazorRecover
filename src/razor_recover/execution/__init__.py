"""Execution layer - PERFORMS authorized recovery actions.

The policy engine decides what is safe; this package acts on it. Nothing here
changes a decision or calls the LLM - it only executes explicit ALLOW decisions
and records the outcome.
"""

from src.razor_recover.execution.exceptions import (
    ExecutionError,
    GatewayError,
    GatewayTimeoutError,
    GatewayUnavailableError,
    NotificationError,
    UnauthorizedExecutionError,
)
from src.razor_recover.execution.gateway import (
    MockPaymentGateway,
    PaymentGateway,
    create_payment_gateway,
)
from src.razor_recover.execution.notification_service import (
    MockNotificationProvider,
    NotificationProvider,
    NotificationService,
)
from src.razor_recover.execution.recovery_service import RecoveryService
from src.razor_recover.execution.retry_service import RetryService
from src.razor_recover.execution.schemas import (
    ExecutionResult,
    ExecutionStatus,
    GatewayChargeResult,
    GatewayOutcome,
    NotificationResult,
    NotificationStatus,
)

__all__ = [
    "RecoveryService",
    "RetryService",
    "NotificationService",
    "MockPaymentGateway",
    "MockNotificationProvider",
    "PaymentGateway",
    "NotificationProvider",
    "create_payment_gateway",
    "ExecutionResult",
    "ExecutionStatus",
    "GatewayChargeResult",
    "GatewayOutcome",
    "NotificationResult",
    "NotificationStatus",
    "ExecutionError",
    "UnauthorizedExecutionError",
    "GatewayError",
    "GatewayTimeoutError",
    "GatewayUnavailableError",
    "NotificationError",
]
