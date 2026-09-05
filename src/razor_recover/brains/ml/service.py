"""Composition root for ML inference: loads models and produces predictions.

Keeps model loading and prediction in one place (dependency injection) so the
workflow layer never deals with model artifacts. Models load lazily so
constructing the service does not require artifacts to exist. Missing artifacts
raise a controlled :class:`MLModelUnavailableError`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel

from razor_recover.brains.ml import features
from razor_recover.brains.ml.model_base import (
    MLModelError,
    ModelArtifactError,
    RecoveryPrediction,
    RiskPrediction,
)
from razor_recover.brains.ml.recovery_model import RecoveryModel
from razor_recover.brains.ml.risk_model import RiskModel
from razor_recover.brains.ml.training import (
    DEFAULT_ARTIFACT_DIR,
    RECOVERY_ARTIFACT_NAME,
    RISK_ARTIFACT_NAME,
)
from razor_recover.core.logger import get_logger

logger = get_logger("brains.ml.service")


class MLModelUnavailableError(MLModelError):
    """Raised when a model artifact is missing and cannot be loaded."""


class Prediction(BaseModel):
    """Structured risk + recovery prediction for one transaction."""

    transaction_external_id: str
    risk_score: float | None = None
    recovery_probability: float | None = None


class PredictionService:
    """Loads and runs both ML models to score a failed transaction."""

    def __init__(
        self,
        risk_model: RiskModel | None = None,
        recovery_model: RecoveryModel | None = None,
        risk_path: str | Path | None = None,
        recovery_path: str | Path | None = None,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._risk_model = risk_model
        self._recovery_model = recovery_model
        base_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ARTIFACT_DIR
        self._risk_path = Path(risk_path) if risk_path else base_dir / RISK_ARTIFACT_NAME
        self._recovery_path = (
            Path(recovery_path) if recovery_path else base_dir / RECOVERY_ARTIFACT_NAME
        )
        self._loaded = risk_model is not None and recovery_model is not None

    def is_available(self) -> bool:
        try:
            self._load()
            return True
        except MLModelError:
            return False

    def predict_single(self, transaction, industry_by_merchant=None) -> Prediction:
        """Score one transaction object (feature adapter exposing ML fields)."""
        self._load()
        external_id = getattr(transaction, "external_id", "unknown")
        vector = features.build_single_transaction_features(
            transaction, industry_by_merchant=industry_by_merchant
        )
        risk: RiskPrediction = self._risk_model.predict(vector, external_id)
        recovery: RecoveryPrediction = self._recovery_model.predict(vector, external_id)
        return Prediction(
            transaction_external_id=external_id,
            risk_score=float(risk.risk_score),
            recovery_probability=float(recovery.recovery_probability),
        )

    def predict_vector(
        self,
        vector,
        external_id: str,
    ) -> Prediction:
        """Score a pre-encoded feature vector."""
        self._load()
        risk: RiskPrediction = self._risk_model.predict(vector, external_id)
        recovery: RecoveryPrediction = self._recovery_model.predict(vector, external_id)
        return Prediction(
            transaction_external_id=external_id,
            risk_score=float(risk.risk_score),
            recovery_probability=float(recovery.recovery_probability),
        )

    # -- internals ----------------------------------------------------------

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            self._risk_model = RiskModel.load(self._risk_path, expected_type="risk")
            self._recovery_model = RecoveryModel.load(
                self._recovery_path, expected_type="recovery"
            )
            self._loaded = True
            logger.info("Loaded ML models from %s", self._risk_path.parent)
        except (ModelArtifactError, FileNotFoundError) as exc:
            raise MLModelUnavailableError(
                f"ML models unavailable at {self._risk_path.parent}: {exc}"
            ) from exc


__all__ = ["PredictionService", "Prediction", "MLModelUnavailableError"]
