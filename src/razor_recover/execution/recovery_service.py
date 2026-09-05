"""RecoveryService - the execution-layer gate and dispatcher.

This is the only place that actually PERFORMS authorized recovery actions. It
independently verifies it received an ``ALLOW`` policy decision (it never trusts
an arbitrary LLM action) and executes only ``PolicyDecision.final_action``.

It writes the executed effects (a ``RecoveryAttempt`` row and, on success, the
transaction status) via the injected DB session. BLOCK / REVIEW decisions are
never executed - they raise :class:`UnauthorizedExecutionError`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from razor_recover.core.logger import get_logger
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction
from razor_recover.execution.exceptions import UnauthorizedExecutionError
from razor_recover.execution.notification_service import NotificationService
from razor_recover.execution.retry_service import RetryService
from razor_recover.execution.schemas import (
    ExecutionResult,
    ExecutionStatus,
    NotificationStatus,
)
from razor_recover.shield.schemas import PolicyDecision, PolicyDecisionType

logger = get_logger("execution.recovery")

# Attempt statuses that mean an action is already in flight -> do not re-dispatch.
_NON_TERMINAL = {"pending", "scheduled"}
# Attempt types that represent a payment retry (used for retry counting).
RETRY_ATTEMPT_TYPES = {"RETRY_NOW", "DELAYED_RETRY"}


class RecoveryService:
    """Executes authorized recovery actions and records their effects."""

    def __init__(
        self,
        retry_service: RetryService | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.retry_service = retry_service or RetryService()
        self.notification_service = notification_service or NotificationService()

    def count_retry_attempts(self, session: Session, transaction_id: int) -> int:
        """Number of existing retry attempts for a transaction (for the shield)."""
        stmt = (
            select(RecoveryAttempt)
            .where(RecoveryAttempt.transaction_id == transaction_id)
            .where(RecoveryAttempt.attempt_type.in_(RETRY_ATTEMPT_TYPES))
        )
        return len(session.scalars(stmt).all())

    def execute(
        self,
        *,
        decision: PolicyDecision,
        session: Session,
        transaction: Transaction,
        reference: str | None = None,
        decision_id: int | None = None,
    ) -> ExecutionResult:
        """Execute an authorized action; raises if the decision is not ALLOW."""
        if decision.decision != PolicyDecisionType.ALLOW:
            raise UnauthorizedExecutionError(
                f"Cannot execute decision={decision.decision.value}; "
                "only ALLOW decisions may be executed."
            )
        final_action = decision.final_action
        if not final_action:
            raise UnauthorizedExecutionError(
                "ALLOW decision has no final_action to execute."
            )

        # Idempotency guard: never re-dispatch an in-flight attempt.
        existing = self._in_flight(session, transaction.id, final_action)
        if existing is not None:
            logger.info(
                "Skipping execution for tx=%s action=%s: already in flight (id=%s)",
                transaction.id, final_action, existing.id,
            )
            return ExecutionResult(
                action=final_action,
                status=ExecutionStatus.SCHEDULED,
                attempt_id=existing.id,
                message="already in progress - skipped duplicate execution",
            )

        started = datetime.now(timezone.utc)
        attempt = RecoveryAttempt(
            transaction_id=transaction.id,
            decision_id=decision_id
            if decision_id is not None
            else self._latest_decision_id(session, transaction.id),
            status="pending",
            attempt_type=final_action,
            started_at=started,
        )
        session.add(attempt)
        session.flush()

        try:
            result = self._run(final_action, transaction, reference or self._new_reference(transaction, final_action))
        except UnauthorizedExecutionError:
            # A safety violation - never record/hide this as a normal failure.
            session.delete(attempt)
            session.flush()
            raise
        except Exception as exc:  # noqa: BLE001 - record failure, do not crash
            logger.exception("Execution failed for tx=%s action=%s", transaction.id, final_action)
            attempt.status = "failed"
            attempt.error_detail = str(exc)
            attempt.completed_at = datetime.now(timezone.utc)
            session.flush()
            return ExecutionResult(
                action=final_action,
                status=ExecutionStatus.FAILED,
                attempt_id=attempt.id,
                error=str(exc),
            )

        attempt.status = result.status.value
        attempt.completed_at = datetime.now(timezone.utc)
        session.flush()

        # Only a successful payment recovery marks the transaction recovered.
        if result.status == ExecutionStatus.RECOVERED:
            transaction.status = "recovered"

        result.attempt_id = attempt.id
        return result

    # -- internals ----------------------------------------------------------

    def _run(
        self, final_action: str, transaction: Transaction, reference: str
    ) -> ExecutionResult:
        amount = float(transaction.amount)
        currency = transaction.currency or "USD"
        method = transaction.payment_method or "card"
        if final_action == "RETRY_NOW":
            return self.retry_service.retry_now(amount, currency, reference, method)
        if final_action == "DELAYED_RETRY":
            return self.retry_service.delayed_retry(amount, currency, reference, method)
        if final_action == "ALTERNATIVE_PAYMENT":
            return self.retry_service.alternative_payment(amount, currency, reference)
        if final_action == "CUSTOMER_NOTIFICATION":
            res = self.notification_service.notify(
                recipient=transaction.customer.email if transaction.customer else "unknown@example.com",
                template="recovery_reminder",
                context={"transaction_external_id": transaction.external_id},
            )
            status = (
                ExecutionStatus.SENT
                if res.status == NotificationStatus.SENT
                else ExecutionStatus.FAILED
            )
            return ExecutionResult(action=final_action, status=status,
                                   message=res.message)
        # MANUAL_REVIEW / STOP should never be ALLOWed by the policy engine.
        raise UnauthorizedExecutionError(
            f"Action {final_action!r} must never be auto-executed."
        )

    def _in_flight(self, session: Session, transaction_id: int, action: str) -> RecoveryAttempt | None:
        stmt = (
            select(RecoveryAttempt)
            .where(RecoveryAttempt.transaction_id == transaction_id)
            .where(RecoveryAttempt.attempt_type == action)
            .where(RecoveryAttempt.status.in_(_NON_TERMINAL))
        )
        return session.scalars(stmt).first()

    def _latest_decision_id(self, session: Session, transaction_id: int) -> int | None:
        stmt = (
            select(RecoveryDecision)
            .where(RecoveryDecision.transaction_id == transaction_id)
            .order_by(RecoveryDecision.id.desc())
            .limit(1)
        )
        obj = session.scalars(stmt).first()
        return obj.id if obj else None

    def _new_reference(self, transaction: Transaction, action: str) -> str:
        return f"{transaction.external_id}:{action}:{datetime.now(timezone.utc).timestamp():.0f}"


__all__ = ["RecoveryService"]
