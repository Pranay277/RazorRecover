"""RecoveryWorkflow orchestrator - coordinates the full vertical slice.

Pipeline:  fetch -> ML -> RAG -> LLM -> Policy -> Execution -> persist -> audit.

Each stage owns its responsibility; the orchestrator only calls leaf services
and assembles a response. It never executes anything itself - execution is
delegated to :class:`RecoveryService`, which independently verifies an ALLOW
decision. A blocked or unavailable upstream stage results in a controlled error
or a fail-closed decision - it never silently fabricates.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from razor_recover.core.logger import get_logger
from razor_recover.db.models.audit import AuditLog
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.transaction import Transaction
from razor_recover.brains.ml.service import MLModelUnavailableError
from razor_recover.brains.llm.exceptions import (
    LLMError,
    InvalidAgentInputError,
)
from razor_recover.execution.recovery_service import RecoveryService
from razor_recover.shield.exceptions import PolicyError
from razor_recover.shield.policy_engine import PolicyEngine
from razor_recover.shield.schemas import PolicyDecision, PolicyDecisionType
from razor_recover.workflow import context as ctx
from razor_recover.workflow.exceptions import (
    LLMStageError,
    MLStageError,
    PolicyStageError,
    TransactionNotFoundError,
)
from razor_recover.workflow.ports import (
    AgentServicePort,
    MerchantPolicyProviderPort,
    PredictionServicePort,
    RagServicePort,
)
from razor_recover.workflow.schemas import EvaluateResponse

logger = get_logger("workflow.orchestrator")

_DECISION_OUTCOME = {
    PolicyDecisionType.ALLOW: "authorized",
    PolicyDecisionType.BLOCK: "blocked",
    PolicyDecisionType.REVIEW: "review",
}
_RETRY_TYPES = {"RETRY_NOW", "DELAYED_RETRY"}


class RecoveryOrchestrator:
    """Coordinates ML/RAG/LLM/Policy/Execution for a single transaction."""

    def __init__(
        self,
        prediction_service: "PredictionServicePort",
        agent_service: "AgentServicePort",
        policy_engine: PolicyEngine,
        recovery_service: RecoveryService,
        merchant_policy_provider: "MerchantPolicyProviderPort",
        rag_service: "RagServicePort | None" = None,
    ) -> None:
        self.prediction_service = prediction_service
        self.agent_service = agent_service
        self.policy_engine = policy_engine
        self.recovery_service = recovery_service
        self.merchant_policy_provider = merchant_policy_provider
        self.rag_service = rag_service

    # -- public --------------------------------------------------------------

    def evaluate(
        self,
        session: Session,
        transaction_id: int,
        request_id: str | None = None,
    ) -> EvaluateResponse:
        rid = request_id or f"re_{uuid4().hex[:12]}"
        transaction = self._fetch_transaction(session, transaction_id)
        logger.info(
            "workflow start transaction_id=%s merchant_id=%s request_id=%s",
            transaction.id,
            transaction.merchant_id,
            rid,
        )

        prediction = self._predict(transaction)
        risk = prediction.risk_score
        recovery = prediction.recovery_probability

        rag_result = self._retrieve(transaction)

        decision_request = ctx.build_decision_request(
            transaction, risk, recovery, rag_result, request_id=rid
        )
        agent_decision = self._decide(decision_request)

        retry_attempts = self.recovery_service.count_retry_attempts(
            session, transaction.id
        )
        merchant_policy = self.merchant_policy_provider.get_policy(
            transaction.merchant.external_id
            if transaction.merchant is not None
            else None
        )
        shield_ctx = ctx.build_shield_context(
            transaction,
            agent_decision,
            merchant_policy,
            risk,
            recovery,
            retry_attempts,
            history_available=True,
        )
        policy_decision = self._authorize(shield_ctx)

        execution = None
        if policy_decision.decision == PolicyDecisionType.ALLOW:
            execution = self.recovery_service.execute(
                decision=policy_decision,
                session=session,
                transaction=transaction,
            )
            logger.info(
                "execution completed transaction_id=%s action=%s status=%s",
                transaction.id, policy_decision.final_action,
                execution.status.value if execution else "n/a",
            )
        else:
            logger.info(
                "no execution transaction_id=%s decision=%s",
                transaction.id, policy_decision.decision.value,
            )

        decision_id = self._persist_decision(session, transaction, agent_decision, policy_decision)
        audit_id = self._audit(
            session, transaction, agent_decision, policy_decision, execution,
            rag_result, risk, recovery, rid,
        )
        session.flush()

        return self._to_response(
            transaction, risk, recovery, agent_decision, policy_decision,
            execution, audit_id,
        )

    # -- stages --------------------------------------------------------------

    def _fetch_transaction(self, session: Session, transaction_id: int) -> Transaction:
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        tx = session.scalars(stmt).first()
        if tx is None:
            raise TransactionNotFoundError(
                f"Transaction {transaction_id} does not exist."
            )
        return tx

    def _predict(self, transaction: Transaction):
        try:
            source = ctx.build_feature_source(transaction)
            return self.prediction_service.predict_single(source)
        except MLModelUnavailableError as exc:
            raise MLStageError(f"ML models unavailable: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - controlled failure
            logger.exception("ML prediction failed tx=%s", transaction.id)
            raise MLStageError(f"ML prediction failed: {exc}") from exc

    def _retrieve(self, transaction: Transaction):
        """Best-effort RAG retrieval; never invents context if it fails."""
        if self.rag_service is None:
            return None
        query = " ".join(
            filter(None, [transaction.failure_code, transaction.failure_reason])
        ).strip() or transaction.external_id
        merchant_id = (
            transaction.merchant.external_id
            if transaction.merchant is not None
            else None
        )
        try:
            return self.rag_service.retrieve(
                query=query, merchant_id=merchant_id, top_k=3
            )
        except Exception as exc:  # noqa: BLE001 - safe fallback
            logger.warning("RAG retrieval unavailable, using empty context: %s", exc)
            return None

    def _decide(self, decision_request):
        try:
            return self.agent_service.recommend(decision_request)
        except InvalidAgentInputError as exc:
            raise LLMStageError(f"Invalid agent input: {exc}") from exc
        except LLMError as exc:
            logger.warning("LLM decision failed: %s", exc)
            raise LLMStageError(f"LLM unavailable: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - controlled failure
            logger.exception("LLM decision failed")
            raise LLMStageError(f"LLM decision failed: {exc}") from exc

    def _authorize(self, shield_ctx) -> PolicyDecision:
        try:
            return self.policy_engine.evaluate(shield_ctx)
        except PolicyError as exc:
            logger.exception("Policy evaluation failed - failing closed")
            raise PolicyStageError(f"Policy evaluation failed: {exc}") from exc

    # -- persistence ---------------------------------------------------------

    def _persist_decision(
        self,
        session: Session,
        transaction: Transaction,
        agent_decision,
        policy_decision: PolicyDecision,
    ) -> int:
        row = RecoveryDecision(
            transaction_id=transaction.id,
            action=policy_decision.requested_action or "",
            outcome=_DECISION_OUTCOME[policy_decision.decision],
            risk_score=policy_decision.risk_score,
            policy_version=policy_decision.policy_version,
            rationale=agent_decision.rationale if agent_decision else None,
            decided_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.flush()
        return row.id

    def _audit(
        self,
        session: Session,
        transaction: Transaction,
        agent_decision,
        policy_decision: PolicyDecision,
        execution,
        rag_result,
        risk: float | None,
        recovery: float | None,
        request_id: str,
    ) -> int:
        detail: dict[str, Any] = {
            "request_id": request_id,
            "transaction_external_id": transaction.external_id,
            "risk_score": risk,
            "recovery_probability": recovery,
            "rag_references": self._rag_references(rag_result),
            "llm_requested_action": policy_decision.requested_action,
            "llm_rationale": agent_decision.rationale if agent_decision else None,
            "policy_decision": policy_decision.decision.value,
            "policy_version": policy_decision.policy_version,
            "policy_reasons": policy_decision.reasons,
            "rule_results": [
                {"rule": r.rule_name, "passed": r.passed,
                 "disposition": r.disposition.value if r.disposition else None}
                for r in policy_decision.rule_results
            ],
            "final_action": policy_decision.final_action,
            "execution_status": execution.status.value if execution else None,
            "execution_message": execution.message if execution else None,
            "attempt_id": execution.attempt_id if execution else None,
        }
        row = AuditLog(
            transaction_id=transaction.id,
            actor="recovery.workflow",
            action=f"recovery.evaluate:{policy_decision.decision.value}",
            detail=json.dumps(detail, default=str),
            occurred_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.flush()
        return row.id

    @staticmethod
    def _rag_references(rag_result) -> list[str] | None:
        if rag_result is None or not getattr(rag_result, "hits", None):
            return None
        return [h.document_id for h in rag_result.hits]

    # -- response ------------------------------------------------------------

    @staticmethod
    def _to_response(
        transaction: Transaction,
        risk: float | None,
        recovery: float | None,
        agent_decision,
        policy_decision: PolicyDecision,
        execution,
        audit_id: int | None,
    ) -> EvaluateResponse:
        return EvaluateResponse(
            transaction_id=transaction.id,
            risk_score=risk,
            recovery_probability=recovery,
            recommended_action=policy_decision.requested_action,
            policy_decision=policy_decision.decision.value,
            authorized_action=policy_decision.final_action,
            execution_status=execution.status.value if execution else None,
            recovery_status=transaction.status,
            rationale=agent_decision.rationale if agent_decision else None,
            policy_reasons=list(policy_decision.reasons),
            audit_id=audit_id,
        )


__all__ = ["RecoveryOrchestrator"]
