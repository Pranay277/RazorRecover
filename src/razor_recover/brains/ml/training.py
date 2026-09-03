"""Reusable training and evaluation flow for the ML models.

Ties together: generating/loading the synthetic dataset -> building features ->
building targets -> stratified train/test split -> training the risk and
recovery models -> computing evaluation metrics -> saving model artifacts.

Everything is reproducible given a fixed seed. Model artifacts are written under
``models/`` by default (a git-ignored directory).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from src.razor_recover.brains.ml import features, targets
from src.razor_recover.brains.ml.model_base import BaseScoringModel
from src.razor_recover.brains.ml.recovery_model import RecoveryModel
from src.razor_recover.brains.ml.risk_model import RiskModel
from src.razor_recover.core.logger import get_logger
from src.razor_recover.synthetic import SyntheticDataConfig, generate_dataset
from src.razor_recover.synthetic.schemas import SyntheticDataset

logger: logging.Logger = get_logger("brains.ml.training")

# Default (git-ignored) artifact directory.
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[3] / "models"

RISK_ARTIFACT_NAME = "risk_model.joblib"
RECOVERY_ARTIFACT_NAME = "recovery_model.joblib"


class ModelMetrics(BaseModel):
    """Evaluation metrics for a single model on the hold-out test split."""

    model_type: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    brier_score: float
    log_loss: float
    positive_rate: float
    confusion_matrix: list[list[int]]


class MLTrainingReport(BaseModel):
    """Summary of a full training run for both models."""

    seed: int
    n_samples: int
    n_train: int
    n_test: int
    n_features: int
    feature_names: list[str]
    excluded_leaked_fields: list[str]
    risk: ModelMetrics
    recovery: ModelMetrics
    risk_artifact_path: str
    recovery_artifact_path: str


class TrainingConfig(BaseModel):
    """Configuration for a training run."""

    dataset_config: SyntheticDataConfig = Field(default_factory=SyntheticDataConfig)
    test_size: float = Field(default=0.25, gt=0.0, lt=1.0)
    random_state: int = 42
    max_iter: int = 1000
    artifact_dir: str | None = None
    save_artifacts: bool = True


def _new_estimator(random_state: int, max_iter: int) -> LogisticRegression:
    return LogisticRegression(
        C=1.0,
        max_iter=max_iter,
        random_state=random_state,
        class_weight="balanced",
    )


@dataclass
class _TrainingResult:
    model: BaseScoringModel
    metrics: ModelMetrics
    artifact_path: str


def _metrics(model_type: str, y_true, y_proba, y_pred) -> ModelMetrics:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return ModelMetrics(
        model_type=model_type,
        accuracy=round(float(accuracy_score(y_true, y_pred)), 6),
        precision=round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        recall=round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        f1=round(float(f1_score(y_true, y_pred, zero_division=0)), 6),
        roc_auc=round(float(roc_auc_score(y_true, y_proba)), 6),
        brier_score=round(float(brier_score_loss(y_true, y_proba)), 6),
        log_loss=round(float(log_loss(y_true, y_proba)), 6),
        positive_rate=round(float(np.mean(y_true)), 6),
        confusion_matrix=[[int(tn), int(fp)], [int(fn), int(tp)]],
    )


def _train_one(
    model_cls,
    model_type: str,
    X_train,
    y_train,
    X_test,
    y_test,
    feature_names_received,
    random_state: int,
    max_iter: int,
    artifact_path: Path,
    save: bool,
) -> _TrainingResult:
    estimator = _new_estimator(random_state, max_iter)
    estimator.fit(X_train, y_train)
    y_proba = estimator.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)
    metrics = _metrics(model_type, y_test, y_proba, y_pred)
    model = model_cls(estimator, feature_names_received)
    saved = ""
    if save:
        saved = str(model.save(artifact_path))
    logger.info(
        "%s model: AUC=%.4f F1=%.4f accuracy=%.4f",
        model_type,
        metrics.roc_auc,
        metrics.f1,
        metrics.accuracy,
    )
    return _TrainingResult(model=model, metrics=metrics, artifact_path=saved)


def _validate_signals(y_recovered: np.ndarray, y_risk: np.ndarray) -> None:
    if len(np.unique(y_recovered)) < 2:
        logger.warning(
            "Recovery labels are (nearly) all one class; check the synthetic "
            "dataset generator - metrics may be meaningless."
        )
    if len(np.unique(y_risk)) < 2:
        logger.warning(
            "Risk labels are (nearly) all one class; metrics may be meaningless."
        )


def train_models(
    config: TrainingConfig | None = None,
    dataset: SyntheticDataset | None = None,
) -> MLTrainingReport:
    """Full train/evaluate/save flow for both the risk and recovery models.

    If ``dataset`` is None, one is generated from ``config.dataset_config``.
    """
    if config is None:
        config = TrainingConfig()

    if dataset is None:
        logger.info(
            "Generating synthetic dataset (%s)", config.dataset_config.model_dump()
        )
        dataset = generate_dataset(config.dataset_config)

    matrix = features.build_feature_matrix(dataset)
    y_recovered = targets.recovery_targets(dataset)
    y_risk = targets.risk_targets(dataset)
    _validate_signals(y_recovered, y_risk)

    X_train, X_test, yr_train, yr_test = train_test_split(
        matrix.X,
        y_recovered,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y_recovered,
    )
    # Same row split for the risk labels (identical indices).
    _, _, yrisk_train, yrisk_test = train_test_split(
        matrix.X,
        y_risk,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y_recovered,
    )

    artifact_dir = Path(config.artifact_dir) if config.artifact_dir else DEFAULT_ARTIFACT_DIR

    risk_result = _train_one(
        RiskModel,
        "risk",
        X_train,
        yrisk_train,
        X_test,
        yrisk_test,
        matrix.feature_names,
        config.random_state,
        config.max_iter,
        artifact_dir / RISK_ARTIFACT_NAME,
        config.save_artifacts,
    )
    recovery_result = _train_one(
        RecoveryModel,
        "recovery",
        X_train,
        yr_train,
        X_test,
        yr_test,
        matrix.feature_names,
        config.random_state,
        config.max_iter,
        artifact_dir / RECOVERY_ARTIFACT_NAME,
        config.save_artifacts,
    )

    report = MLTrainingReport(
        seed=config.dataset_config.seed,
        n_samples=matrix.X.shape[0],
        n_train=int(X_train.shape[0]),
        n_test=int(X_test.shape[0]),
        n_features=matrix.n_features,
        feature_names=matrix.feature_names,
        excluded_leaked_fields=list(features.EXCLUDED_LEAKED_FIELDS),
        risk=risk_result.metrics,
        recovery=recovery_result.metrics,
        risk_artifact_path=risk_result.artifact_path,
        recovery_artifact_path=recovery_result.artifact_path,
    )
    logger.info("Training run complete. %s", report.model_dump())
    return report
