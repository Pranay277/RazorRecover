"""Customer notification abstraction for the execution layer.

Like the gateway, the execution layer depends on a :class:`NotificationProvider`
protocol with a deterministic mock. No real email/SMS provider is contacted.
"""

from __future__ import annotations

import logging
from typing import Protocol

from razor_recover.core.logger import get_logger
from razor_recover.execution.exceptions import NotificationError
from razor_recover.execution.schemas import NotificationResult, NotificationStatus

logger = get_logger("execution.notification")


class NotificationProvider(Protocol):
    """A reusable provider for delivering notifications."""

    name: str

    def send(
        self,
        recipient: str,
        template: str,
        context: dict | None = None,
    ) -> NotificationResult: ...


class MockNotificationProvider:
    """Deterministic mock notification provider (never sends anything real)."""

    name = "mock"

    def __init__(self, default_status: NotificationStatus | str = NotificationStatus.SENT):
        self.default_status = NotificationStatus(default_status)
        self.sent: list[dict] = []

    def send(
        self,
        recipient: str,
        template: str,
        context: dict | None = None,
    ) -> NotificationResult:
        self.sent.append(
            {"recipient": recipient, "template": template, "context": context or {}}
        )
        logger.info("Mock notification %s -> %s", template, recipient)
        return NotificationResult(
            status=self.default_status,
            channel="email",
            message=f"notification {self.default_status.value}",
        )


class NotificationService:
    """Executes a customer-notification action through the provider."""

    def __init__(self, provider: NotificationProvider | None = None) -> None:
        self.provider = provider or MockNotificationProvider()

    def notify(
        self,
        recipient: str,
        template: str,
        context: dict | None = None,
    ) -> NotificationResult:
        try:
            return self.provider.send(recipient, template, context or {})
        except NotificationError:
            raise
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.exception("Notification delivery failed")
            raise NotificationError(f"Notification failed: {exc}") from exc


__all__ = [
    "NotificationProvider",
    "MockNotificationProvider",
    "NotificationService",
]
