"""Retry / alternative-payment execution for the execution layer.

Performs recovery actions against the payment gateway once they are authorized.
Retries map to a gateway charge; alternative payment maps to an alternative
recovery path; delayed retry is recorded as scheduled without an immediate
gateway call.
"""

from __future__ import annotations

import logging

from razor_recover.core.logger import get_logger
from razor_recover.execution.gateway import (
    MockPaymentGateway,
    PaymentGateway,
    create_payment_gateway,
)
from razor_recover.execution.schemas import (
    ExecutionResult,
    ExecutionStatus,
    GatewayOutcome,
)

logger = get_logger("execution.retry")


class RetryService:
    """Executes payment-retry style actions against the gateway."""

    def __init__(self, gateway: PaymentGateway | None = None) -> None:
        self.gateway = gateway or create_payment_gateway(provider="mock")

    def retry_now(
        self,
        amount: float,
        currency: str,
        reference: str,
        method: str = "card",
    ) -> ExecutionResult:
        result = self.gateway.charge(
            amount=amount, currency=currency, reference=reference, method=method
        )
        return self._map_gateway(result, action="RETRY_NOW")

    def delayed_retry(
        self,
        amount: float,
        currency: str,
        reference: str,
        method: str = "card",
    ) -> ExecutionResult:
        # MVP: record as scheduled; no immediate gateway interaction.
        logger.info("DELAYED_RETRY scheduled for reference=%s", reference)
        return ExecutionResult(
            action="DELAYED_RETRY",
            status=ExecutionStatus.SCHEDULED,
            message="delayed retry scheduled",
            details={"reference": reference},
        )

    def alternative_payment(
        self,
        amount: float,
        currency: str,
        reference: str,
        method: str = "netbanking",
    ) -> ExecutionResult:
        result = self.gateway.charge(
            amount=amount, currency=currency, reference=reference, method=method
        )
        return self._map_gateway(result, action="ALTERNATIVE_PAYMENT")

    @staticmethod
    def _map_gateway(result, action: str) -> ExecutionResult:
        if result.outcome == GatewayOutcome.SUCCESS:
            status = ExecutionStatus.RECOVERED
        elif result.outcome == GatewayOutcome.TIMEOUT:
            status = ExecutionStatus.TIMEOUT
        else:
            status = ExecutionStatus.FAILED
        return ExecutionResult(
            action=action,
            status=status,
            message=result.message,
            error=result.error_code,
            details={"reference": result.reference},
        )


__all__ = ["RetryService"]
