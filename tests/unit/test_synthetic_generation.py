"""Unit tests for synthetic dataset generation (determinism, size,
relationships, failure categories, and record-level consistency).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.razor_recover.synthetic import SyntheticDataConfig, generate_dataset
from src.razor_recover.synthetic.constants import (
    ATTEMPT_STATUSES,
    DECISION_OUTCOMES,
    FAILURE_CATEGORIES,
    PAYMENT_METHODS,
)
from src.razor_recover.synthetic.schemas import SyntheticDataset


def _small_config(**overrides) -> SyntheticDataConfig:
    defaults = dict(n_merchants=5, n_customers=10, n_transactions=60, seed=11)
    defaults.update(overrides)
    return SyntheticDataConfig(**defaults)


def test_same_seed_produces_identical_dataset():
    a = generate_dataset(_small_config())
    b = generate_dataset(_small_config())
    assert a == b
    assert a.merchants == b.merchants
    assert a.transactions == b.transactions
    assert a.decisions == b.decisions
    assert a.recovery_attempts == b.recovery_attempts


def test_different_seed_produces_different_dataset():
    a = generate_dataset(_small_config(seed=1))
    b = generate_dataset(_small_config(seed=2))
    assert a.transactions != b.transactions


def test_configurable_dataset_size():
    cfg = _small_config(n_merchants=7, n_customers=25, n_transactions=200)
    ds = generate_dataset(cfg)
    assert len(ds.merchants) == 7
    assert len(ds.customers) == 25
    assert len(ds.transactions) == 200
    assert len(ds.decisions) == 200


def test_config_rejects_zero_sizes():
    with pytest.raises(ValidationError):
        SyntheticDataConfig(n_merchants=0)
    with pytest.raises(ValidationError):
        SyntheticDataConfig(n_transactions=0)


def test_valid_relationships_between_entities():
    ds = generate_dataset(_small_config())
    merchant_ids = {m.external_id for m in ds.merchants}
    customer_ids = {c.external_id for c in ds.customers}

    for tx in ds.transactions:
        assert tx.merchant_external_id in merchant_ids
        assert tx.customer_external_id in customer_ids

    # Every transaction has exactly one decision.
    decision_txs = {d.transaction_external_id for d in ds.decisions}
    assert len(decision_txs) == len(ds.transactions)

    # Every decision points to a real transaction.
    all_tx = {t.external_id for t in ds.transactions}
    assert decision_txs == all_tx


def test_unique_transaction_ids():
    ds = generate_dataset(_small_config())
    ids = [t.external_id for t in ds.transactions]
    assert len(ids) == len(set(ids))


def test_valid_failure_categories():
    ds = generate_dataset(_small_config())
    for tx in ds.transactions:
        assert tx.failure_code in FAILURE_CATEGORIES
        assert tx.failure_reason


def test_failure_categories_non_uniform_distribution():
    # Large sample should include a mix of categories (not all identical).
    ds = generate_dataset(SyntheticDataConfig(n_transactions=2000, seed=5))
    seen = {t.failure_code for t in ds.transactions}
    assert len(seen) >= 3


def test_valid_payment_methods_and_gateways():
    ds = generate_dataset(_small_config())
    for tx in ds.transactions:
        assert tx.payment_method in PAYMENT_METHODS
        assert tx.gateway
        assert tx.attempt_number >= 1


def test_transaction_attempt_consistency():
    """Attempts per transaction must equal attempt_number, and final attempt
    status must match whether the transaction was recovered."""
    ds = generate_dataset(_small_config())
    attempts_by_tx: dict[str, list] = {}
    for attempt in ds.recovery_attempts:
        attempts_by_tx.setdefault(attempt.transaction_external_id, []).append(attempt)

    for tx in ds.transactions:
        attempts = attempts_by_tx.get(tx.external_id, [])
        assert len(attempts) == tx.attempt_number
        for attempt in attempts:
            assert attempt.status in ATTEMPT_STATUSES


def test_recovery_outcome_consistency():
    """A transaction marked recovered must have a successful final attempt."""
    ds = generate_dataset(_small_config())
    by_tx: dict[str, list] = {}
    for attempt in ds.recovery_attempts:
        by_tx.setdefault(attempt.transaction_external_id, []).append(attempt)

    for tx in ds.transactions:
        attempts = by_tx[tx.external_id]
        final_status = attempts[-1].status
        if tx.status == "recovered":
            assert final_status == "success"
        else:
            assert final_status == "failed"


def test_decision_outcome_valid():
    ds = generate_dataset(_small_config())
    for d in ds.decisions:
        assert d.outcome in DECISION_OUTCOMES
        assert 0 <= d.risk_score < 1


def test_customer_history_counts_are_derived():
    ds = generate_dataset(_small_config())
    # For each customer, history of a given tx must equal the count of that
    # customer's prior (already-accounted) transactions.
    seen: dict[str, int] = {}
    for tx in ds.transactions:
        count_before = seen.get(tx.customer_external_id, 0)
        prior_failed = tx.history.previous_failed_count
        prior_success = tx.history.previous_successful_count
        assert prior_failed >= 0 and prior_success >= 0
        assert prior_failed + prior_success == count_before
        seen[tx.customer_external_id] = count_before + 1


def test_timestamps_are_aware_and_recent():
    ds = generate_dataset(_small_config())
    now = datetime.now(timezone.utc)
    for tx in ds.transactions:
        assert tx.timestamp.tzinfo is not None
        assert tx.timestamp <= now


def test_amounts_are_positive():
    ds = generate_dataset(_small_config())
    for tx in ds.transactions:
        assert tx.amount > 0


def test_dataset_is_validated():
    ds = generate_dataset(_small_config())
    # Re-validating through the model proves records conform to the schema.
    assert isinstance(ds, SyntheticDataset)
    SyntheticDataset.model_validate(ds.model_dump())
