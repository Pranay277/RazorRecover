"""Risk model: predicts the recovery risk score of a failed payment.

Input : feature vector built from evaluation-time information (see
``features.py``). Output : ``risk_score`` in [0, 1] = probability the payment is
a loss (not recovered).
"""

from razor_recover.brains.ml.model_base import BaseScoringModel, RiskPrediction


class RiskModel(BaseScoringModel):
    _MODEL_TYPE = "risk"
    _POSITIVE_LABEL = 1  # high_risk (payment lost)
    _PredictionCls = RiskPrediction
    _result_field = "risk_score"
