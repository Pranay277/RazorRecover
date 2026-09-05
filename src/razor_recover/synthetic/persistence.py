"""Database persistence for synthetic datasets.

Separate from generation. This module maps synthetic records onto the
existing SQLAlchemy ORM models and writes them through the shared
``SessionLocal`` / session infrastructure. No second connection system is
introduced, and generation logic is not duplicated here.
"""

from sqlalchemy.orm import Session

from razor_recover.core.logger import get_logger
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.merchant import Merchant
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction
from razor_recover.synthetic.schemas import SyntheticDataset

logger = get_logger("synthetic.persistence")


def write_dataset(
    session: Session,
    dataset: SyntheticDataset,
    clear_existing: bool = False,
) -> int:
    """Persist a synthetic dataset and return the total records written.

    ``clear_existing`` optionally wipes existing transaction-scoped data first
    (in dependency order) so repeated generation runs stay isolated. It does
    not drop tables.
    """
    if clear_existing:
        _clear(session)

    merchant_ids = _persist_merchants(session, dataset)
    customer_ids = _persist_customers(session, dataset)

    tx_id_by_external: dict[str, int] = _persist_transactions(
        session, dataset, customer_ids, merchant_ids
    )
    session.flush()

    decision_ids = _persist_decisions(session, dataset, tx_id_by_external)
    session.flush()

    _persist_attempts(session, dataset, tx_id_by_external, decision_ids)
    session.flush()

    total = dataset.total_entities
    logger.info(
        "Persisted %d records (merchants=%d customers=%d transactions=%d "
        "decisions=%d attempts=%d)",
        total,
        len(dataset.merchants),
        len(dataset.customers),
        len(dataset.transactions),
        len(dataset.decisions),
        len(dataset.recovery_attempts),
    )
    return total


def _persist_merchants(session: Session, dataset: SyntheticDataset) -> dict[str, int]:
    ids: dict[str, int] = {}
    for sample in dataset.merchants:
        obj = Merchant(
            external_id=sample.external_id,
            name=sample.name,
            industry=sample.industry,
            status=sample.status,
        )
        session.add(obj)
        session.flush()
        ids[sample.external_id] = obj.id
    return ids


def _persist_customers(session: Session, dataset: SyntheticDataset) -> dict[str, int]:
    ids: dict[str, int] = {}
    for sample in dataset.customers:
        obj = Customer(
            external_id=sample.external_id,
            name=sample.name,
            email=sample.email,
            status=sample.status,
        )
        session.add(obj)
        session.flush()
        ids[sample.external_id] = obj.id
    return ids


def _persist_transactions(
    session: Session,
    dataset: SyntheticDataset,
    customer_ids: dict[str, int],
    merchant_ids: dict[str, int],
) -> dict[str, int]:
    ids: dict[str, int] = {}
    for sample in dataset.transactions:
        obj = Transaction(
            external_id=sample.external_id,
            customer_id=customer_ids[sample.customer_external_id],
            merchant_id=merchant_ids[sample.merchant_external_id],
            amount=sample.amount,
            currency=sample.currency,
            status=sample.status,
            failure_code=sample.failure_code,
            failure_reason=sample.failure_reason,
            attempted_at=sample.timestamp,
            payment_method=sample.payment_method,
            gateway=sample.gateway,
            attempt_number=sample.attempt_number,
        )
        session.add(obj)
        session.flush()
        ids[sample.external_id] = obj.id
    return ids


def _persist_decisions(
    session: Session,
    dataset: SyntheticDataset,
    tx_id_by_external: dict[str, int],
) -> dict[str, int]:
    ids: dict[str, int] = {}
    for sample in dataset.decisions:
        obj = RecoveryDecision(
            transaction_id=tx_id_by_external[sample.transaction_external_id],
            action=sample.action,
            outcome=sample.outcome,
            risk_score=sample.risk_score,
            rationale=sample.rationale,
            decided_at=sample.decided_at,
        )
        session.add(obj)
        session.flush()
        ids[sample.transaction_external_id] = obj.id
    return ids


def _persist_attempts(
    session: Session,
    dataset: SyntheticDataset,
    tx_id_by_external: dict[str, int],
    decision_ids: dict[str, int],
) -> None:
    for sample in dataset.recovery_attempts:
        obj = RecoveryAttempt(
            transaction_id=tx_id_by_external[sample.transaction_external_id],
            decision_id=decision_ids.get(sample.transaction_external_id),
            status=sample.status,
            attempt_type=sample.attempt_type,
            error_detail=sample.error_detail,
            started_at=sample.started_at,
            completed_at=sample.completed_at,
        )
        session.add(obj)


def _clear(session: Session) -> None:
    """Delete transaction-scoped rows in dependency order."""
    session.query(RecoveryAttempt).delete()
    session.query(RecoveryDecision).delete()
    session.query(Transaction).delete()
    session.query(Customer).delete()
    session.query(Merchant).delete()
