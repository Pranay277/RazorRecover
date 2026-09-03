"""Target definitions for the ML models.

Each target is derived from the synthetic dataset's recovery outcome, which is
the ground-truth label produced by the Phase 3A generator.

Risk model
    ``high_risk``  -> 1 when the failed payment is NOT eventually recovered
    (i.e. it is a financial loss). This is the standard definition of recovery
    risk: the probability the payment is lost.

Recovery model
    ``recovered``  -> 1 when the failed payment IS eventually recovered.

The two targets are complementary views of the same underlying event
(``high_risk == not recovered``), which is a natural consequence of the domain:
risk of loss and probability of recovery are opposite sides of the same coin.
"""

import numpy as np

from src.razor_recover.synthetic.schemas import SyntheticDataset


def recovery_targets(dataset: SyntheticDataset) -> np.ndarray:
    """Binary labels: 1 = payment eventually recovered, else 0.

    Aligned with ``dataset.transactions`` order, matching the feature matrix.
    """
    return np.asarray(
        [1.0 if tx.status == "recovered" else 0.0 for tx in dataset.transactions],
        dtype=np.float64,
    )


def risk_targets(dataset: SyntheticDataset) -> np.ndarray:
    """Binary labels: 1 = high recovery risk (payment lost), else 0.

    Defined as the complement of the recovery outcome.
    """
    rec = recovery_targets(dataset)
    return 1.0 - rec
