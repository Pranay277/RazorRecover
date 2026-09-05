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

from razor_recover.synthetic import constants as c
from razor_recover.synthetic.config import SyntheticDataConfig
from razor_recover.synthetic.generators import (
    AmountGenerator,
    CustomerGenerator,
    FailureCodeGenerator,
    HistoryGenerator,
    MerchantGenerator,
)
from razor_recover.synthetic.schemas import (
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
        amount = amount_gen.generate(currency)
        payment_method = rng.choice(c.PAYMENT_METHODS)
        gateway = rng.choice(c.GATEWAYS)

        # Non-uniform attempt counts: 1 attempt is most common, more are rarer.
        attempt_number = int(rng.choices([1, 2, 3, 4], weights=[60, 25, 10, 5], k=1)[0])

        # Derive historical behavior from that customer's prior transactions.
        prior = by_customer[customer.external_id]
        previous_failed = sum(1 for tx in prior if tx.status != "recovered")
        history = history_gen.derive(
            previous_count=len(prior),
            success_ratio=(
                (len(prior) - previous_failed) / len(prior) if prior else 1.0
            ),
        )

        # Whether this payment is eventually recovered drives both the decision
        # outcome and the final attempt status (recovery outcome consistency).
        # The outcome is a realistic function of information available at
        # evaluation time (failure category, customer history, amount, gateway,
        # payment method) plus more attempts => more chances. It deliberately
        # does NOT depend only on the leaked attempt count, so a non-leaky ML
        # model trained on evaluation-time features has genuine signal.
        recovered = _decide_recovery(
            rng, attempt_number, failure_code, history, float(amount), gateway,
            payment_method,
        )

        tx_external_id = f"tx_{i:06d}"
        transaction = SyntheticTransaction(
            external_id=tx_external_id,
            customer_external_id=customer.external_id,
            merchant_external_id=merchant.external_id,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            gateway=gateway,
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


# Base (unconditional) recovery likelihood per failure category. Higher values
# mean the failure is "easier" to recover by retrying / asking for a new card;
# hard-decline categories (insufficient_funds, bank_declined) are harder.
_RECOVERY_BASE_RATE: dict[str, float] = {
    "network_timeout": 0.70,
    "gateway_error": 0.65,
    "expired_card": 0.60,
    "authentication_failed": 0.55,
    "limit_exceeded": 0.50,
    "unknown": 0.45,
    "bank_declined": 0.38,
    "insufficient_funds": 0.30,
}

# Small, fixed per-gateway recovery adjustment (gateway reliability).
_GATEWAY_EFFECT: dict[str, float] = {
    "stripe": 0.05, "adyen": 0.04, "braintree": 0.02, "razorpay": 0.03,
    "paypal": 0.00, "worldpay": -0.02, "chase": -0.04, "barclays": -0.05,
}

# Small per-payment-method recovery adjustment.
_PAYMENT_METHOD_EFFECT: dict[str, float] = {
    "card": 0.03, "wallet": 0.02, "upi": 0.00, "bank_transfer": -0.03,
}


def _decide_recovery(
    rng: random.Random,
    attempt_number: int,
    failure_code: str,
    history,
    amount: float,
    gateway: str,
    payment_method: str,
) -> bool:
    """Decide whether a failed payment is eventually recovered.

    The outcome depends on information available at evaluation time (failure
    category, customer history, amount, gateway, payment method) plus the fact
    that more attempts give more chances. Only the seeded ``rng`` introduces
    stochasticity, keeping generation fully reproducible.
    """
    base = _RECOVERY_BASE_RATE.get(failure_code, 0.45)

    # More attempts => more chances to eventually recover.
    chance = base + (attempt_number - 1) * 0.08

    # Customers with a stronger prior success history are easier to recover.
    n_prev = history.previous_successful_count + history.previous_failed_count
    if n_prev > 0:
        ratio = history.previous_successful_count / n_prev
        chance += (ratio - 0.5) * 0.30

    # Larger amounts are slightly harder to recover.
    chance -= min(0.12, amount / 2500.0)

    # Gateway / payment method reliability modifiers.
    chance += _GATEWAY_EFFECT.get(gateway, 0.0)
    chance += _PAYMENT_METHOD_EFFECT.get(payment_method, 0.0)

    chance = max(0.05, min(0.92, chance))
    return rng.random() < chance


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
