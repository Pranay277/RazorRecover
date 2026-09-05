"""Repository-style read queries for the dashboard.

Encapsulates all SELECT logic so the API endpoints do not contain SQL.
Read-only by contract: every method only queries.

Related models: :class:`Transaction`, :class:`RecoveryDecision`,
:class:`RecoveryAttempt`, :class:`AuditLog`.
"""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from razor_recover.db.models.audit import AuditLog
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction
from razor_recover.schemas.dashboard import (
    AuditListResponse,
    AuditLogItem,
    CustomerReference,
    MerchantReference,
    RecoveryAttemptRead,
    RecoveryAttemptSummary,
    RecoveryDecisionRead,
    RecoveryDecisionSummary,
    ShieldRuleResult,
    SummaryResponse,
    TransactionDetail,
    TransactionListItem,
    TransactionListResponse,
)


class DashboardReadService:
    """Pure read service exposing persisted data for the merchant dashboard."""

    # -- transactions list ----------------------------------------------------

    def list_transactions(
        self,
        session: Session,
        *,
        status: str | None = None,
        merchant_id: int | None = None,
        customer_id: int | None = None,
        payment_method: str | None = None,
        gateway: str | None = None,
        failure_code: str | None = None,
        search: str | None = None,
        attempted_from: datetime | None = None,
        attempted_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> TransactionListResponse:
        total = self._count_transactions(
            session,
            status=status,
            merchant_id=merchant_id,
            customer_id=customer_id,
            payment_method=payment_method,
            gateway=gateway,
            failure_code=failure_code,
            search=search,
            attempted_from=attempted_from,
            attempted_to=attempted_to,
        )
        stmt = (
            select(Transaction)
            .options(joinedload(Transaction.merchant), joinedload(Transaction.customer))
            .order_by(Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        stmt = self._apply_filters(
            stmt,
            status=status,
            merchant_id=merchant_id,
            customer_id=customer_id,
            payment_method=payment_method,
            gateway=gateway,
            failure_code=failure_code,
            search=search,
            attempted_from=attempted_from,
            attempted_to=attempted_to,
        )
        rows = session.scalars(stmt).all()

        latest_decisions = self._latest_decisions(session, [t.id for t in rows])
        latest_attempts = self._latest_attempts(session, [t.id for t in rows])

        items = []
        for tx in rows:
            merchant_ext = tx.merchant.external_id if tx.merchant is not None else None
            customer_ext = tx.customer.external_id if tx.customer is not None else None
            items.append(
                TransactionListItem.model_validate(tx).model_copy(
                    update={
                        "merchant_external_id": merchant_ext,
                        "customer_external_id": customer_ext,
                        "latest_decision": latest_decisions.get(tx.id),
                        "latest_attempt": latest_attempts.get(tx.id),
                    }
                )
            )
        return TransactionListResponse(items=items, total=total, limit=limit, offset=offset)

    # -- transaction detail ---------------------------------------------------

    def get_transaction_detail(
        self, session: Session, transaction_id: int
    ) -> TransactionDetail | None:
        stmt = (
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .options(
                joinedload(Transaction.merchant),
                joinedload(Transaction.customer),
                selectinload(Transaction.decisions),
                selectinload(Transaction.recovery_attempts),
            )
        )
        tx = session.scalars(stmt).first()
        if tx is None:
            return None

        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.transaction_id == transaction_id)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        )
        audit_rows = session.scalars(audit_stmt).all()

        customer = None
        if tx.customer is not None:
            customer = CustomerReference.model_validate(tx.customer)
        merchant = None
        if tx.merchant is not None:
            merchant = MerchantReference.model_validate(tx.merchant)

        decisions = sorted(
            (RecoveryDecisionRead.model_validate(d) for d in tx.decisions),
            key=lambda d: d.decided_at,
            reverse=True,
        )
        attempts = sorted(
            (RecoveryAttemptRead.model_validate(a) for a in tx.recovery_attempts),
            key=lambda a: a.id,
            reverse=True,
        )

        evaluate_meta = self._latest_evaluate_meta(audit_rows)
        recovery_probability = evaluate_meta.get("recovery_probability")
        rule_rows = evaluate_meta.get("rule_results")
        shield_rule_results = (
            [ShieldRuleResult.model_validate(r) for r in rule_rows]
            if isinstance(rule_rows, list)
            else None
        )

        return TransactionDetail.model_validate(tx).model_copy(
            update={
                "merchant_external_id": tx.merchant.external_id if tx.merchant else None,
                "customer_external_id": tx.customer.external_id if tx.customer else None,
                "customer": customer,
                "merchant": merchant,
                "decisions": decisions,
                "attempts": attempts,
                "audit_logs": [self._audit_item(a, tx.external_id) for a in audit_rows],
                "recovery_probability": recovery_probability,
                "shield_rule_results": shield_rule_results,
            }
        )

    # -- summary --------------------------------------------------------------

    def get_summary(self, session: Session) -> SummaryResponse:
        status_counts = self._counts_grouped(session, Transaction.status)
        total_tx = int(status_counts.pop("total", 0))

        attempt_status_counts = self._counts_grouped(session, RecoveryAttempt.status)
        total_attempts = int(attempt_status_counts.pop("total", 0))

        decision_outcome_counts, decisions_total = self._counts_grouped_total(
            session, RecoveryDecision.outcome
        )
        decision_action_counts, _ = self._counts_grouped_total(
            session, RecoveryDecision.action
        )
        risk_buckets = self._risk_buckets(session)

        amount_by_status = self._amounts_grouped(session)
        failed_amount = str(amount_by_status.get("failed", Decimal("0.00")))
        recovered_amount = str(amount_by_status.get("recovered", Decimal("0.00")))
        total_amount = str(sum(amount_by_status.values(), Decimal("0.00")))

        return SummaryResponse(
            total_transactions=total_tx,
            transactions_by_status=status_counts,
            total_recovery_attempts=total_attempts,
            recovery_attempts_by_status=attempt_status_counts,
            recovery_decisions_total=decisions_total,
            recovery_decisions_by_outcome=decision_outcome_counts,
            recovery_decisions_by_action=decision_action_counts,
            recovery_decisions_by_risk_bucket=risk_buckets,
            failed_amount=failed_amount,
            recovered_amount=recovered_amount,
            total_amount=total_amount,
        )

    # -- audit trail ----------------------------------------------------------

    def list_audit_logs(
        self,
        session: Session,
        *,
        transaction_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditListResponse:
        total_stmt = select(func.count()).select_from(AuditLog)
        if transaction_id is not None:
            total_stmt = total_stmt.where(AuditLog.transaction_id == transaction_id)
        total = int(session.scalar(total_stmt))

        stmt = (
            select(AuditLog, Transaction.external_id)
            .outerjoin(Transaction, Transaction.id == AuditLog.transaction_id)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if transaction_id is not None:
            stmt = stmt.where(AuditLog.transaction_id == transaction_id)

        rows = session.execute(stmt).all()
        items = [self._audit_item(log, ext) for log, ext in rows]
        return AuditListResponse(items=items, total=total, limit=limit, offset=offset)

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _apply_filters(stmt, *, status, merchant_id, customer_id,
                       payment_method, gateway, failure_code,
                       search=None, attempted_from=None, attempted_to=None):
        if status is not None:
            stmt = stmt.where(Transaction.status == status)
        if merchant_id is not None:
            stmt = stmt.where(Transaction.merchant_id == merchant_id)
        if customer_id is not None:
            stmt = stmt.where(Transaction.customer_id == customer_id)
        if payment_method is not None:
            stmt = stmt.where(Transaction.payment_method == payment_method)
        if gateway is not None:
            stmt = stmt.where(Transaction.gateway == gateway)
        if failure_code is not None:
            stmt = stmt.where(Transaction.failure_code == failure_code)
        if search:
            term = f"%{search.strip()}%"
            customer_ids = select(Customer.id).where(
                Customer.external_id.ilike(term)
            )
            stmt = stmt.where(
                Transaction.external_id.ilike(term)
                | Transaction.customer_id.in_(customer_ids)
            )
        if attempted_from is not None:
            stmt = stmt.where(Transaction.attempted_at >= attempted_from)
        if attempted_to is not None:
            stmt = stmt.where(Transaction.attempted_at < attempted_to)
        return stmt

    def _count_transactions(self, session: Session, **filters) -> int:
        stmt = select(func.count()).select_from(Transaction)
        stmt = self._apply_filters(stmt, **filters)
        return int(session.scalar(stmt))

    @staticmethod
    def _counts_grouped(session: Session, column):
        result = {}
        rows = session.execute(
            select(column, func.count()).group_by(column)
        ).all()
        total = 0
        for value, count in rows:
            if value is None:
                continue
            total += int(count)
            result[str(value)] = int(count)
        result["total"] = total
        return result

    @staticmethod
    def _counts_grouped_total(session: Session, column):
        """Like :meth:`_counts_grouped` but returns (counts, total) separately,
        so the summary can keep a distinct total for decisions."""
        counts = DashboardReadService._counts_grouped(session, column)
        total = int(counts.pop("total", 0))
        return counts, total

    @staticmethod
    def _amounts_grouped(session: Session) -> dict[str, Decimal]:
        rows = session.execute(
            select(Transaction.status, func.sum(Transaction.amount))
            .group_by(Transaction.status)
        ).all()
        return {str(status): Decimal(str(value or 0)) for status, value in rows if status}

    @staticmethod
    def _latest_decisions(
        session: Session, transaction_ids: list[int]
    ) -> dict[int, RecoveryDecisionSummary]:
        """Most recent decision per transaction id (insertion order)."""
        if not transaction_ids:
            return {}
        stmt = (
            select(RecoveryDecision.transaction_id, RecoveryDecision)
            .where(RecoveryDecision.transaction_id.in_(transaction_ids))
            .order_by(RecoveryDecision.id.desc())
        )
        latest: dict[int, RecoveryDecisionSummary] = {}
        for tx_id, row in session.execute(stmt).all():
            if tx_id not in latest:
                latest[tx_id] = RecoveryDecisionSummary.model_validate(row)
        return latest

    @staticmethod
    def _latest_attempts(
        session: Session, transaction_ids: list[int]
    ) -> dict[int, RecoveryAttemptSummary]:
        """Most recent recovery attempt per transaction id (insertion order)."""
        if not transaction_ids:
            return {}
        stmt = (
            select(RecoveryAttempt.transaction_id, RecoveryAttempt)
            .where(RecoveryAttempt.transaction_id.in_(transaction_ids))
            .order_by(RecoveryAttempt.id.desc())
        )
        latest: dict[int, RecoveryAttemptSummary] = {}
        for tx_id, row in session.execute(stmt).all():
            if tx_id not in latest:
                latest[tx_id] = RecoveryAttemptSummary.model_validate(row)
        return latest

    @staticmethod
    def _latest_evaluate_meta(audit_rows: list[AuditLog]) -> dict:
        """Return the detail dict of the newest evaluate audit event, if any."""
        for log in audit_rows:
            if not log.detail:
                continue
            try:
                parsed = json.loads(log.detail)
            except (ValueError, TypeError):
                continue
            if isinstance(parsed, dict) and (
                "recovery_probability" in parsed or "rule_results" in parsed
            ):
                return parsed
        return {}

    @staticmethod
    def _risk_buckets(session: Session) -> dict[str, int]:
        """Bucket persisted decision risk scores: low/medium/high/unknown."""
        buckets = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
        for (score,) in session.execute(select(RecoveryDecision.risk_score)).all():
            if score is None:
                buckets["unknown"] += 1
            elif score < Decimal("0.33"):
                buckets["low"] += 1
            elif score < Decimal("0.66"):
                buckets["medium"] += 1
            else:
                buckets["high"] += 1
        return buckets

    @staticmethod
    def _audit_item(log: AuditLog, external_id: str | None) -> AuditLogItem:
        detail = None
        parsed = None
        if log.detail:
            try:
                loaded = json.loads(log.detail)
            except (ValueError, TypeError):
                loaded = None
            if isinstance(loaded, dict):
                parsed = loaded
                detail = parsed
            elif loaded is not None:
                detail = {"raw": loaded}
        return AuditLogItem(
            id=log.id,
            transaction_id=log.transaction_id,
            transaction_external_id=external_id,
            actor=log.actor,
            action=log.action,
            detail=detail,
            occurred_at=log.occurred_at,
            created_at=log.created_at,
            llm_requested_action=(parsed or {}).get("llm_requested_action"),
            policy_decision=(parsed or {}).get("policy_decision"),
            execution_status=(parsed or {}).get("execution_status"),
        )


__all__ = ["DashboardReadService"]
