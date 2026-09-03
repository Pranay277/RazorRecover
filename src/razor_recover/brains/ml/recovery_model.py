"""Recovery model: predicts the probability a failed payment is recovered.

Input : feature vector built from evaluation-time information (see
``features.py``). Output : ``recovery_probability`` in [0, 1] = probability the
payment is eventually recovered.
"""

from src.razor_recover.brains.ml.model_base import (
    BaseScoringModel,
    RecoveryPrediction,
)


class RecoveryModel(BaseScoringModel):
    _MODEL_TYPE = "recovery"
    _POSITIVE_LABEL = 1  # recovered
    _PredictionCls = RecoveryPrediction
    _result_field = "recovery_probability"
