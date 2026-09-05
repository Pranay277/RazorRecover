"""Reusable, seedable generator components.

Each generator owns a slice of the dataset and receives a shared
``random.Random`` instance so the whole pipeline is reproducible when the
seed is fixed. Generators are independent of database persistence.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from razor_recover.synthetic import constants as c
from razor_recover.synthetic.schemas import (
    SyntheticCustomer,
    SyntheticHistory,
    SyntheticMerchant,
)


class MerchantGenerator:
    """Generates realistic merchants."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def generate(self, count: int) -> list[SyntheticMerchant]:
        merchants: list[SyntheticMerchant] = []
        for i in range(count):
            name = self._rng.choice(c.MERCHANT_NAMES)
            merchants.append(
                SyntheticMerchant(
                    external_id=f"mch_{i:06d}",
                    name=name,
                    industry=self._rng.choice(c.INDUSTRIES),
                )
            )
        return merchants


class CustomerGenerator:
    """Generates realistic customers."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def _email(self, first: str, last: str) -> str:
        domain = self._rng.choice(c.DOMAINS)
        return f"{first.lower()}.{last.lower()}@{domain}"

    def generate(self, count: int) -> list[SyntheticCustomer]:
        customers: list[SyntheticCustomer] = []
        for i in range(count):
            first = self._rng.choice(c.CUSTOMER_FIRST_NAMES)
            last = self._rng.choice(c.CUSTOMER_LAST_NAMES)
            customers.append(
                SyntheticCustomer(
                    external_id=f"cst_{i:06d}",
                    name=f"{first} {last}",
                    email=self._email(first, last),
                )
            )
        return customers


class AmountGenerator:
    """Generates transaction amounts following a skewed, realistic distribution."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def generate(self, currency: str) -> Decimal:
        # Most payments are small; a few are large. Skew via normal distribution.
        raw = max(1.0, self._rng.normalvariate(60.0, 45.0))
        # Occasionally scale up to represent larger B2B/infra payments.
        if self._rng.random() < 0.05:
            raw *= self._rng.uniform(5.0, 20.0)
        return Decimal(str(round(raw, 2)))


class FailureCodeGenerator:
    """Generates a failure category and a matching human-readable reason."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def generate(self) -> tuple[str, str]:
        code = self._rng.choices(c.FAILURE_CATEGORIES, weights=c.FAILURE_WEIGHTS, k=1)[0]
        return code, c.FAILURE_REASONS[code]


class HistoryGenerator:
    """Derives a customer's historical payment behavior from their transactions.

    This is intentionally computed from the already-generated transaction
    history so that the aggregate reflects the dataset consistently, rather
    than being an independent random value.
    """

    def derive(
        self, previous_count: int, success_ratio: float
    ) -> SyntheticHistory:
        successful = round(previous_count * success_ratio)
        failed = previous_count - successful
        return SyntheticHistory(
            previous_failed_count=max(failed, 0),
            previous_successful_count=max(successful, 0),
        )
