"""Synthetic dataset orchestration.

``generate_dataset`` wires the reusable generator components together and
enforces cross-record consistency (valid merchant/customer/transaction
relationships, transaction/attempt consistency, and recovery outcome
consistency). Generation is fully deterministic for a fixed seed.

This module does NOT persist anything; see ``persistence`` for DB writes.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.razor_recover.synthetic import constants as c
from src.razor_recover.synthetic.config import SyntheticDataConfig
from src.razor_recover.synthetic.generators import (
    AmountGenerator,
    CustomerGenerator,
    FailureCodeGenerator,
    HistoryGenerator,
    MerchantGenerator,
)
from src.razor_recover.synthetic.schemas import (
    SyntheticDataset,
    SyntheticDecision,
    SyntheticRecoveryAttempt,
    SyntheticTransaction,
)

# Fixed anchor for generating timestamps so output is fully reproducible
# (independent of the wall clock). Spreads transactions over the prior year.
_ANCHOR = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
DAY_SPAN = 365


def _timestamp_ago(rng: random.Random) -> datetime:
    days = rng.uniform(0, DAY_SPAN)
    seconds = rng.uniform(0, 86400)
    return _ANCHOR - timedelta(days=days, seconds=seconds)


def generate_dataset(
    config: SyntheticDataConfig | None = None,
) -> SyntheticDataset:
    """Generate a complete, internally consistent synthetic dataset."""
    if config is None:
        config = SyntheticDataConfig()

    rng = random.Random(config.seed)

    merchant_gen = MerchantGenerator(rng)
    customer_gen = CustomerGenerator(rng)
    amount_gen = AmountGenerator(rng)
    failure_gen = FailureCodeGenerator(rng)
    history_gen = HistoryGenerator()

    merchants = merchant_gen.generate(config.n_merchants)
    customers = customer_gen.generate(config.n_customers)

    by_customer: dict[str, list[SyntheticTransaction]] = {cst.external_id: [] for cst in customers}

    transactions: list[SyntheticTransaction] = []
    decisions: list[SyntheticDecision] = []
    recovery_attempts: list[SyntheticRecoveryAttempt] = []

    for i in range(config.n_transactions):
        customer = rng.choice(customers)
        merchant = rng.choice(merchants)
        currency = rng.choice(c.CURRENCIES)
        timestamp = _timestamp_ago(rng)

        failure_code, failure_reason = failure_gen.generate()

        # Non-uniform attempt counts: 1 attempt is most common, more are rarer.
        attempt_number = int(rng.choices([1, 2, 3, 4], weights=[60, 25, 10, 5], k=1)[0])

        # Whether this payment is eventually recovered drives both the decision
        # outcome and the final attempt status (recovery outcome consistency).
        recovered = _decide_recovery(rng, attempt_number)

        # Derive historical behavior from that customer's prior transactions.
        prior = by_customer[customer.external_id]
        previous_failed = sum(1 for tx in prior if tx.status != "recovered")
        history = history_gen.derive(
            previous_count=len(prior),
            success_ratio=(
                (len(prior) - previous_failed) / len(prior) if prior else 1.0
            ),
        )

        tx_external_id = f"tx_{i:06d}"
        transaction = SyntheticTransaction(
            external_id=tx_external_id,
            customer_external_id=customer.external_id,
            merchant_external_id=merchant.external_id,
            amount=amount_gen.generate(currency),
            currency=currency,
            payment_method=rng.choice(c.PAYMENT_METHODS),
            gateway=rng.choice(c.GATEWAYS),
            timestamp=timestamp,
            failure_code=failure_code,
            failure_reason=failure_reason,
            attempt_number=attempt_number,
            status="recovered" if recovered else "failed",
            history=history,
        )
        transactions.append(transaction)
        by_customer[customer.external_id].append(transaction)

        # Recovery decision.
        action = _choose_action(rng, failure_code)
        decision = SyntheticDecision(
            transaction_external_id=tx_external_id,
            action=action,
            outcome="authorized" if recovered else rng.choice(
                ["authorized", "denied"]
            ),
            risk_score=_risk_score(rng),
            rationale=_rationale(failure_code, recovered),
            decided_at=timestamp + timedelta(minutes=rng.uniform(1, 1440)),
        )
        decisions.append(decision)

        # Payment/recovery attempts consistent with the outcome.
        for attempt_idx in range(1, attempt_number + 1):
            attempt = SyntheticRecoveryAttempt(
                transaction_external_id=tx_external_id,
                status=_attempt_status(attempt_idx, attempt_number, recovered),
                attempt_type=_attempt_type(rng, failure_code),
                started_at=timestamp + timedelta(minutes=attempt_idx * 15),
                completed_at=timestamp + timedelta(minutes=attempt_idx * 15 + 3),
                error_detail=(
                    failure_reason if not (attempt_idx == attempt_number and recovered) else None
                ),
            )
            recovery_attempts.append(attempt)

    return SyntheticDataset(
        seed=config.seed,
        merchants=merchants,
        customers=customers,
        transactions=transactions,
        decisions=decisions,
        recovery_attempts=recovery_attempts,
    )


def _decide_recovery(rng: random.Random, attempt_number: int) -> bool:
    # More attempts increase the chance a recovery actually succeeds.
    base_chance = {1: 0.40, 2: 0.55, 3: 0.70, 4: 0.80}.get(attempt_number, 0.60)
    return rng.random() < base_chance


def _choose_action(rng: random.Random, failure_code: str) -> str:
    if failure_code in ("expired_card", "authentication_failed"):
        return "request_new_card"
    if failure_code in ("network_timeout", "gateway_error"):
        return "retry"
    if failure_code == "insufficient_funds":
        return rng.choice(["dunning_email", "retry"])
    return rng.choice(c.RECOVERY_ACTIONS)


def _risk_score(rng: random.Random) -> Decimal:
    # Risk skewed low for most, occasionally higher.
    value = max(0.0, min(0.9999, rng.betavariate(2, 5)))
    return Decimal(str(round(value, 4)))


def _rationale(failure_code: str, recovered: bool) -> str:
    if recovered:
        return f"Recovery authorized for {failure_code}"
    return f"Recovery not authorized or exhausted for {failure_code}"


def _attempt_status(
    attempt_idx: int, attempt_number: int, recovered: bool
) -> str:
    if attempt_idx < attempt_number:
        return "failed"
    # Final attempt: success only if the transaction was recovered.
    return "success" if recovered else "failed"


def _attempt_type(rng: random.Random, failure_code: str) -> str:
    if failure_code in ("expired_card", "authentication_failed"):
        return "card_revalidation"
    if failure_code == "insufficient_funds":
        return "balance_retry"
    return "card_retry"
