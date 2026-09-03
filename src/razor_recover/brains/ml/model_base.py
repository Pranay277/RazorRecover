"""Shared base for the scalar scoring ML models.

Provides save/load, prediction, error handling and structured output used by
both :class:`RiskModel` and :class:`RecoveryModel`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from pydantic import BaseModel, Field

from src.razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.ml")


class MLModelError(Exception):
    """Base error for the ML layer."""


class InvalidInputError(MLModelError):
    """Raised when a prediction receives malformed feature input."""


class MissingFeatureError(InvalidInputError):
    """Raised when a required feature is missing from the input."""


class ModelArtifactError(MLModelError):
    """Raised when a model artifact is missing, corrupt, or of the wrong type."""


class RiskPrediction(BaseModel):
    """Structured result of a risk-model prediction."""

    transaction_external_id: str
    risk_score: float = Field(ge=0.0, le=1.0)


class RecoveryPrediction(BaseModel):
    """Structured result of a recovery-model prediction."""

    transaction_external_id: str
    recovery_probability: float = Field(ge=0.0, le=1.0)


def _validate_feature_vector(feature_vector, expected_n: int) -> np.ndarray:
    if feature_vector is None:
        raise MissingFeatureError("Feature vector is required (missing 'X' input).")
    arr = np.asarray(feature_vector, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2:
        raise InvalidInputError(
            f"Feature input must be 1-D or 2-D, got ndim={arr.ndim}."
        )
    if arr.shape[1] != expected_n:
        raise InvalidInputError(
            f"Expected {expected_n} features, but received {arr.shape[1]}. "
            "Rebuild features with the same feature builder."
        )
    if not np.all(np.isfinite(arr)):
        raise InvalidInputError("Feature vector contains non-finite values (NaN/inf).")
    return arr


class BaseScoringModel:
    """A probabilistic binary scoring model (positive class probability output).

    Concrete subclasses define ``_POSITIVE_LABEL`` and a prediction type.
    """

    _MODEL_TYPE: str = "base"
    _PredictionCls = BaseModel
    _result_field: str = "probability"

    def __init__(self, estimator: Any, feature_names: list[str]) -> None:
        self.estimator = estimator
        self.feature_names = list(feature_names)

    # -- prediction ---------------------------------------------------------
    def predict(self, feature_vector, transaction_external_id: str):
        """Return a structured prediction with a probability in [0, 1].

        ``feature_vector`` is the encoded features produced by the feature
        builder (1-D for a single row, 2-D for a batch).
        """
        arr = _validate_feature_vector(feature_vector, len(self.feature_names))
        try:
            proba = self.estimator.predict_proba(arr)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Prediction failed")
            raise MLModelError(f"Prediction failed: {exc}") from exc

        pos_index = self._positive_class_index()
        result = float(np.clip(proba[:, pos_index][0], 0.0, 1.0))
        return self._PredictionCls(
            transaction_external_id=transaction_external_id,
            **{self._result_field: result},
        )

    def predict_many(
        self, X: np.ndarray, transaction_external_ids: list[str]
    ) -> list[BaseModel]:
        arr = _validate_feature_vector(X, len(self.feature_names))
        if len(transaction_external_ids) != arr.shape[0]:
            raise InvalidInputError(
                "Number of transaction ids must match number of feature rows."
            )
        try:
            proba = self.estimator.predict_proba(arr)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Batch prediction failed")
            raise MLModelError(f"Batch prediction failed: {exc}") from exc
        pos_index = self._positive_class_index()
        return [
            self._PredictionCls(
                transaction_external_id=tid,
                **{self._result_field: float(np.clip(proba[i, pos_index], 0.0, 1.0))},
            )
            for i, tid in enumerate(transaction_external_ids)
        ]

    def _positive_class_index(self) -> int:
        classes = list(self.estimator.classes_)
        for i, cls in enumerate(classes):
            if int(cls) == self._POSITIVE_LABEL:
                return i
        raise MLModelError(
            f"Positive class {self._POSITIVE_LABEL} not present in estimator classes {classes}."
        )

    # -- persistence --------------------------------------------------------
    def _artifact_payload(self) -> dict[str, Any]:
        return {
            "model_type": self._MODEL_TYPE,
            "estimator": self.estimator,
            "feature_names": self.feature_names,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._artifact_payload(), path)
        logger.info("Saved %s model to %s", self._MODEL_TYPE, path)
        return path

    @classmethod
    def load(cls, path: str | Path, expected_type: str | None = None) -> "BaseScoringModel":
        path = Path(path)
        if not path.exists():
            raise ModelArtifactError(f"Model artifact not found: {path}")
        try:
            payload = joblib.load(path)
        except Exception as exc:
            raise ModelArtifactError(
                f"Failed to load model artifact {path}: {exc}"
            ) from exc
        if not isinstance(payload, dict) or "estimator" not in payload:
            raise ModelArtifactError(
                f"Model artifact {path} has an unexpected format."
            )
        artifact_type = payload.get("model_type")
        if expected_type and artifact_type != expected_type:
            raise ModelArtifactError(
                f"Artifact is '{artifact_type}', expected '{expected_type}' at {path}."
            )
        return cls(
            estimator=payload["estimator"],
            feature_names=payload["feature_names"],
        )
