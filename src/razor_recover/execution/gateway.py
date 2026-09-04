"""Payment gateway abstraction.

The execution layer depends only on the :class:`PaymentGateway` protocol so the
rest of the application is never hard-wired to a concrete provider.
:class:`MockPaymentGateway` simulates SUCCESS/FAILED/TIMEOUT deterministically
and never contacts a real payment system. Future real providers implement the
same interface.
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.razor_recover.core.logger import get_logger
from src.razor_recover.execution.schemas import GatewayChargeResult, GatewayOutcome

logger = get_logger("execution.gateway")


class PaymentGateway(Protocol):
    """Reusable interface every payment gateway must satisfy."""

    name: str

    def is_available(self) -> bool: ...
    def charge(
        self,
        amount: float,
        currency: str,
        reference: str,
        method: str = "card",
        metadata: dict | None = None,
    ) -> GatewayChargeResult: ...


class MockPaymentGateway:
    """Deterministic simulated payment gateway.

    Behavior is configured per-``reference`` via :meth:`configure` (or a base
    ``default_outcome``). Outcomes are the enum values SUCCESS / FAILED /
    TIMEOUT. Never touches a real payment system.
    """

    name = "mock"

    def __init__(
        self,
        default_outcome: GatewayOutcome | str = GatewayOutcome.SUCCESS,
        outcomes: dict[str, GatewayOutcome | str] | None = None,
    ) -> None:
        self.default_outcome = GatewayOutcome(default_outcome)
        self._outcomes: dict[str, GatewayOutcome] = {
            k: GatewayOutcome(v) for k, v in (outcomes or {}).items()
        }
        self.calls: list[dict] = []

    def configure(self, reference: str, outcome: GatewayOutcome | str) -> None:
        """Set a deterministic outcome for a specific charge reference."""
        self._outcomes[reference] = GatewayOutcome(outcome)

    def is_available(self) -> bool:
        return True

    def charge(
        self,
        amount: float,
        currency: str,
        reference: str,
        method: str = "card",
        metadata: dict | None = None,
    ) -> GatewayChargeResult:
        self.calls.append(
            {
                "amount": amount,
                "currency": currency,
                "reference": reference,
                "method": method,
                "metadata": metadata,
            }
        )
        outcome = self._outcomes.get(reference, self.default_outcome)
        logger.info(
            "Mock gateway outcome=%s for reference=%s", outcome.value, reference
        )
        return GatewayChargeResult(
            outcome=outcome,
            reference=reference,
            message=(
                "charge succeeded"
                if outcome == GatewayOutcome.SUCCESS
                else f"charge {outcome.value.lower()}"
            ),
            error_code=None if outcome == GatewayOutcome.SUCCESS else outcome.value,
        )


def create_payment_gateway(
    provider: str = "mock",
    default_outcome: GatewayOutcome | str = GatewayOutcome.SUCCESS,
) -> PaymentGateway:
    """Factory: build a payment gateway (mock by default for this MVP)."""
    name = (provider or "mock").lower().strip()
    if name == "mock":
        return MockPaymentGateway(default_outcome=default_outcome)
    raise ValueError(f"Unknown payment gateway provider: {provider!r}")


__all__ = [
    "PaymentGateway",
    "MockPaymentGateway",
    "create_payment_gateway",
]
