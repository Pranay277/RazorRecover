"""Tests for synthetic dataset persistence.

Uses the PostgreSQL isolated-session fixture (matching the project's ORM
insertion tests) so writes roll back and never pollute real data. SQLite is
not used for inserts because BigInteger surrogate keys do not autoincrement
there.
"""

from razor_recover.synthetic import generate_dataset, write_dataset
from razor_recover.synthetic.config import SyntheticDataConfig
from razor_recover.db.models.customer import Customer
from razor_recover.db.models.decision import RecoveryDecision
from razor_recover.db.models.merchant import Merchant
from razor_recover.db.models.recovery import RecoveryAttempt
from razor_recover.db.models.transaction import Transaction


def _dataset():
    config = SyntheticDataConfig(
        n_merchants=4, n_customers=8, n_transactions=40, seed=9
    )
    return generate_dataset(config)


def _count(session, model) -> int:
    return session.query(model).count()


def test_write_dataset_populates_all_tables(postgres_session_isolated):
    dataset = _dataset()
    written = write_dataset(postgres_session_isolated, dataset, clear_existing=True)

    assert written == dataset.total_entities
    assert _count(postgres_session_isolated, Merchant) == len(dataset.merchants)
    assert _count(postgres_session_isolated, Customer) == len(dataset.customers)
    assert _count(postgres_session_isolated, Transaction) == len(dataset.transactions)
    assert _count(postgres_session_isolated, RecoveryDecision) == len(dataset.decisions)
    assert _count(postgres_session_isolated, RecoveryAttempt) == len(
        dataset.recovery_attempts
    )


def test_persisted_transactions_keep_fields(postgres_session_isolated):
    dataset = _dataset()
    write_dataset(postgres_session_isolated, dataset, clear_existing=True)

    external = dataset.transactions[0].external_id
    tx = (
        postgres_session_isolated.query(Transaction)
        .filter(Transaction.external_id == external)
        .one()
    )
    sample = dataset.transactions[0]
    assert tx.payment_method == sample.payment_method
    assert tx.gateway == sample.gateway
    assert tx.attempt_number == sample.attempt_number
    assert tx.amount == sample.amount


def test_persisted_relationships(postgres_session_isolated):
    dataset = _dataset()
    write_dataset(postgres_session_isolated, dataset, clear_existing=True)

    tx = postgres_session_isolated.query(Transaction).first()
    assert tx.customer is not None
    assert tx.merchant is not None
    assert tx.decisions  # at least one decision
    assert tx.recovery_attempts  # at least one attempt


def test_clear_existing_wipes_transaction_scoped_data(postgres_session_isolated):
    write_dataset(postgres_session_isolated, _dataset(), clear_existing=True)
    first_total = _count(postgres_session_isolated, Transaction)
    assert first_total > 0

    # Re-run with clear_existing: counts should not accumulate.
    write_dataset(postgres_session_isolated, _dataset(), clear_existing=True)
    assert _count(postgres_session_isolated, Transaction) == first_total
