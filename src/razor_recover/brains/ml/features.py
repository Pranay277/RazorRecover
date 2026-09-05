"""Explicit, reusable feature building for the ML layer (no target leakage).

Only information available at evaluation time for a failed payment is treated
as a legitimate feature. Fields that only become known *after* the recovery
process begins are deliberately excluded because they leak the target:

* ``status`` (final transaction status / whether it was recovered)
* ``attempt_number`` (total number of attempts is future information)
* decision ``outcome`` / decision ``risk_score`` / decision ``rationale``
* recovery attempts (each attempt's status/type/errors)

The feature set is defined explicitly below so feature selection is auditable
and reusable across models and training runs.
"""

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from razor_recover.synthetic import constants as c
from razor_recover.synthetic.schemas import SyntheticDataset

# ---------------------------------------------------------------------------
# Explicit feature configuration
# ---------------------------------------------------------------------------

# Numeric (continuous / count) features, all known at evaluation time.
_NUMERIC_FEATURES: list[str] = [
    "log_amount",
    "previous_failed_count",
    "previous_successful_count",
    "history_success_ratio",
]

# Categorical features, one-hot encoded from the fixed source pools so the
# output dimension is identical regardless of which categories appear in a
# given dataset (consistent, explainable, deterministic).
_CATEGORICAL_FEATURES: dict[str, list[str]] = {
    "failure_code": c.FAILURE_CATEGORIES,
    "currency": c.CURRENCIES,
    "payment_method": c.PAYMENT_METHODS,
    "gateway": c.GATEWAYS,
    "merchant_industry": c.INDUSTRIES,
}

# Fields that are intentionally NOT used as features (documented for tests).
EXCLUDED_LEAKED_FIELDS: list[str] = [
    "status",
    "attempt_number",
    "decision_outcome",
    "decision_risk_score",
    "recovery_attempts",
]


@dataclass(frozen=True)
class FeatureMatrix:
    """Structured feature matrix aligned with its source transactions."""

    X: np.ndarray
    feature_names: list[str]
    transaction_external_ids: list[str]

    @property
    def shape(self) -> tuple[int, int]:
        return self.X.shape

    @property
    def n_features(self) -> int:
        return self.X.shape[1]


def feature_names() -> list[str]:
    """The full, ordered list of feature names used by every model."""
    cols = list(_NUMERIC_FEATURES)
    for cat_values in _CATEGORICAL_FEATURES.values():
        cols.extend(cat_values)
    return cols


def _offsets() -> dict[str, int]:
    offsets: dict[str, int] = {}
    running = len(_NUMERIC_FEATURES)
    for cat in _CATEGORICAL_FEATURES:
        offsets[cat] = running
        running += len(_CATEGORICAL_FEATURES[cat])
    return offsets


def _build_row(
    tx,
    industry_by_merchant: Mapping[str, str],
    offsets: dict[str, int],
    n_cols: int,
) -> list[float]:
    row = [0.0] * n_cols

    prev_failed = tx.history.previous_failed_count
    prev_success = tx.history.previous_successful_count
    total = prev_failed + prev_success
    success_ratio = (prev_success / total) if total > 0 else 1.0

    # log-amount for better numerical conditioning with linear models.
    row[0] = round(float(np.log1p(float(tx.amount).real)), 6)
    row[1] = float(prev_failed)
    row[2] = float(prev_success)
    row[3] = round(success_ratio, 6)

    industry = industry_by_merchant.get(tx.merchant_external_id, "unknown")

    for cat, value in (
        ("failure_code", tx.failure_code),
        ("currency", tx.currency),
        ("payment_method", tx.payment_method),
        ("gateway", tx.gateway),
        ("merchant_industry", industry),
    ):
        base = offsets[cat]
        values = _CATEGORICAL_FEATURES[cat]
        if value in values:
            row[base + values.index(value)] = 1.0
    return row


def _default_industry_lookup(tx) -> dict[str, str]:
    return {tx.merchant_external_id: "unknown"}


def build_feature_matrix(dataset: SyntheticDataset) -> FeatureMatrix:
    """Build an explicit feature matrix from a synthetic dataset.

    Joins each transaction with its merchant (for industry). Output order is
    stable and deterministic per ``feature_names()``.
    """
    industry_by_merchant = {m.external_id: m.industry for m in dataset.merchants}
    offsets = _offsets()
    n_cols = len(_NUMERIC_FEATURES) + sum(
        len(v) for v in _CATEGORICAL_FEATURES.values()
    )

    rows = [_build_row(tx, industry_by_merchant, offsets, n_cols) for tx in dataset.transactions]
    ids = [tx.external_id for tx in dataset.transactions]
    X = np.asarray(rows, dtype=np.float64)
    return FeatureMatrix(X=X, feature_names=feature_names(), transaction_external_ids=ids)


def build_single_transaction_features(
    transaction,
    industry_by_merchant: Mapping[str, str] | None = None,
) -> np.ndarray:
    """Build an encoded feature row for a single transaction (for inference).

    Accepts a :class:`SyntheticTransaction` (or any object exposing the same
    attributes) and returns a 1-D feature vector matching ``feature_names()``.
    If ``industry_by_merchant`` (from ``merchant_industry_lookup``) is not
    provided, the merchant industry is treated as ``unknown``.
    """
    lookup = (
        industry_by_merchant
        if industry_by_merchant is not None
        else _default_industry_lookup(transaction)
    )
    return np.asarray(
        _build_row(
            transaction,
            lookup,
            _offsets(),
            len(_NUMERIC_FEATURES) + sum(len(v) for v in _CATEGORICAL_FEATURES.values()),
        ),
        dtype=np.float64,
    )


def merchant_industry_lookup(dataset: SyntheticDataset) -> dict[str, str]:
    """Public helper mapping merchant ids to industries (reused at inference)."""
    return {m.external_id: m.industry for m in dataset.merchants}


__all__ = [
    "FeatureMatrix",
    "feature_names",
    "build_feature_matrix",
    "build_single_transaction_features",
    "merchant_industry_lookup",
    "EXCLUDED_LEAKED_FIELDS",
]
