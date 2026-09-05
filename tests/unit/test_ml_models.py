"""Unit tests for the ML layer: feature generation, leakage, deterministic
training, prediction range, error handling, artifact save/load, and evaluation.
"""

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from razor_recover.brains.ml import features, targets
from razor_recover.brains.ml.features import (
    EXCLUDED_LEAKED_FIELDS,
    build_feature_matrix,
    build_single_transaction_features,
    feature_names,
)
from razor_recover.brains.ml.model_base import (
    InvalidInputError,
    MissingFeatureError,
    ModelArtifactError,
)
from razor_recover.brains.ml.recovery_model import RecoveryModel
from razor_recover.brains.ml.risk_model import RiskModel
from razor_recover.brains.ml.training import TrainingConfig, train_models
from razor_recover.synthetic import SyntheticDataConfig, generate_dataset


def _dataset(**overrides):
    cfg = dict(n_merchants=8, n_customers=40, n_transactions=400, seed=11)
    cfg.update(overrides)
    return generate_dataset(SyntheticDataConfig(**cfg))


def _small_training(**overrides):
    cfg = dict(n_transactions=600, seed=11, save_artifacts=False)
    cfg.update(overrides)
    return train_models(TrainingConfig(**cfg))


# ---------------------------------------------------------------------------
# Feature generation
# ---------------------------------------------------------------------------

def test_feature_matrix_dimensions():
    ds = _dataset()
    fm = build_feature_matrix(ds)
    assert fm.X.shape[0] == len(ds.transactions)
    assert fm.X.shape[1] == len(feature_names())
    assert fm.transaction_external_ids == [t.external_id for t in ds.transactions]


def test_feature_matrix_is_numeric_and_on_hot():
    fm = build_feature_matrix(_dataset())
    assert np.issubdtype(fm.X.dtype, np.floating)
    # One-hot columns are exactly 0 or 1; numeric columns vary.
    onehot_start = 4  # after the 4 numeric features
    onehot = fm.X[:, onehot_start:]
    assert set(np.unique(onehot)).issubset({0.0, 1.0})
    # Each one-hot block has exactly one '1' per row.
    assert onehot.shape[1] == _one_hot_cardinality()


def _one_hot_cardinality():
    from razor_recover.synthetic.constants import (
        CURRENCIES, GATEWAYS, INDUSTRIES, PAYMENT_METHODS, FAILURE_CATEGORIES,
    )
    return (
        len(FAILURE_CATEGORIES) + len(CURRENCIES) + len(PAYMENT_METHODS)
        + len(GATEWAYS) + len(INDUSTRIES)
    )


def test_feature_names_are_explicit_and_stable():
    names = feature_names()
    assert "log_amount" in names
    assert "failure_code" not in names  # one-hot block uses category names
    assert "insufficient_funds" in names
    assert len(names) == len(set(names))


def test_single_transaction_features_match_matrix():
    ds = _dataset()
    fm = build_feature_matrix(ds)
    tx = ds.transactions[0]
    lookup = features.merchant_industry_lookup(ds)
    row = build_single_transaction_features(tx, industry_by_merchant=lookup)
    assert row.shape == (len(feature_names()),)
    assert np.allclose(row, fm.X[0])


# ---------------------------------------------------------------------------
# No target leakage
# ---------------------------------------------------------------------------

def test_leaked_fields_are_excluded():
    for leaked in EXCLUDED_LEAKED_FIELDS:
        assert leaked not in feature_names()


def test_feature_matrix_does_not_contain_target_or_future_info():
    ds = _dataset()
    fm = build_feature_matrix(ds)
    # No feature derives from the final outcome.
    for name in EXCLUDED_LEAKED_FIELDS:
        assert name not in fm.feature_names


def test_targets_are_derived_from_outcome_only():
    ds = _dataset()
    y_rec = targets.recovery_targets(ds)
    y_risk = targets.risk_targets(ds)
    expected_rec = np.array([1.0 if t.status == "recovered" else 0.0 for t in ds.transactions])
    assert np.array_equal(y_rec, expected_rec)
    assert np.array_equal(y_risk, 1.0 - expected_rec)


def test_targets_aligned_with_feature_matrix():
    ds = _dataset()
    fm = build_feature_matrix(ds)
    y_rec = targets.recovery_targets(ds)
    assert fm.X.shape[0] == y_rec.shape[0]


# ---------------------------------------------------------------------------
# Deterministic training
# ---------------------------------------------------------------------------

def test_training_is_reproducible_with_same_seed():
    a = _small_training(dataset_config=SyntheticDataConfig(n_transactions=600, seed=9))
    b = _small_training(dataset_config=SyntheticDataConfig(n_transactions=600, seed=9))
    assert a.risk.roc_auc == b.risk.roc_auc
    assert a.recovery.roc_auc == b.recovery.roc_auc
    assert a.risk.accuracy == b.risk.accuracy


def test_training_metrics_are_reasonable_not_perfect():
    rep = _small_training()
    # Honest expectation: real non-leaky signal but not a fabricated perfect
    # classifier. A near-perfect AUC here would indicate target leakage.
    assert 0.5 < rep.risk.roc_auc < 0.99
    assert 0.5 < rep.recovery.roc_auc < 0.99
    assert rep.risk.accuracy < 0.99
    assert rep.n_features == len(feature_names())


# ---------------------------------------------------------------------------
# Model training produces working models
# ---------------------------------------------------------------------------

def test_trained_models_predict_in_range():
    ds = _dataset(n_transactions=600)
    fm = build_feature_matrix(ds)

    est = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
    est.fit(fm.X, targets.risk_targets(ds))
    risk = RiskModel(est, fm.feature_names)

    pred = risk.predict(fm.X[0], fm.transaction_external_ids[0])
    assert 0.0 <= pred.risk_score <= 1.0
    assert pred.transaction_external_id == fm.transaction_external_ids[0]


def test_recovery_and_risk_predictions():
    ds = _dataset(n_transactions=600)
    fm = build_feature_matrix(ds)
    matrix = fm.X
    ids = fm.transaction_external_ids

    est_risk = LogisticRegression(max_iter=1000, random_state=1, class_weight="balanced")
    est_risk.fit(matrix, targets.risk_targets(ds))
    risk = RiskModel(est_risk, fm.feature_names)
    rp = risk.predict(matrix[0], ids[0])
    assert 0.0 <= rp.risk_score <= 1.0
    assert rp.transaction_external_id == ids[0]
    many = risk.predict_many(matrix, ids)
    assert len(many) == len(ids)
    assert all(0.0 <= m.risk_score <= 1.0 for m in many)

    est_rec = LogisticRegression(max_iter=1000, random_state=1, class_weight="balanced")
    est_rec.fit(matrix, targets.recovery_targets(ds))
    recovery = RecoveryModel(est_rec, fm.feature_names)
    cp = recovery.predict(matrix[1], ids[1])
    assert 0.0 <= cp.recovery_probability <= 1.0
    assert cp.transaction_external_id == ids[1]


# ---------------------------------------------------------------------------
# Invalid / missing input handling
# ---------------------------------------------------------------------------

def test_predict_missing_input_raises():
    ds = _dataset(n_transactions=300)
    fm = build_feature_matrix(ds)
    est = LogisticRegression(max_iter=1000, random_state=1)
    est.fit(fm.X, targets.recovery_targets(ds))
    model = RecoveryModel(est, fm.feature_names)
    with pytest.raises(MissingFeatureError):
        model.predict(None, "tx")


def test_predict_wrong_feature_count_raises():
    ds = _dataset(n_transactions=300)
    fm = build_feature_matrix(ds)
    est = LogisticRegression(max_iter=1000, random_state=1)
    est.fit(fm.X, targets.recovery_targets(ds))
    model = RecoveryModel(est, fm.feature_names)
    with pytest.raises(InvalidInputError):
        model.predict(np.zeros(fm.n_features - 1), "tx")


def test_predict_nonfinite_raises():
    ds = _dataset(n_transactions=300)
    fm = build_feature_matrix(ds)
    est = LogisticRegression(max_iter=1000, random_state=1)
    est.fit(fm.X, targets.recovery_targets(ds))
    model = RecoveryModel(est, fm.feature_names)
    bad = fm.X[0].copy()
    bad[0] = np.nan
    with pytest.raises(InvalidInputError):
        model.predict(bad, "tx")


def test_predict_mismatched_ids_count_raises():
    ds = _dataset(n_transactions=300)
    fm = build_feature_matrix(ds)
    est = LogisticRegression(max_iter=1000, random_state=1)
    est.fit(fm.X, targets.recovery_targets(ds))
    model = RecoveryModel(est, fm.feature_names)
    with pytest.raises(InvalidInputError):
        model.predict_many(fm.X, ["only-one-id"])


# ---------------------------------------------------------------------------
# Model save / load
# ---------------------------------------------------------------------------

def test_model_save_and_load_roundtrip(tmp_path):
    rep = train_models(
        TrainingConfig(
            dataset_config=SyntheticDataConfig(n_transactions=400, seed=3),
            artifact_dir=str(tmp_path / "artifacts"),
            save_artifacts=True,
        )
    )
    assert tmp_path.joinpath("artifacts", "risk_model.joblib").exists()
    assert tmp_path.joinpath("artifacts", "recovery_model.joblib").exists()

    risk = RiskModel.load(rep.risk_artifact_path, expected_type="risk")
    recovery = RecoveryModel.load(rep.recovery_artifact_path, expected_type="recovery")
    assert risk.feature_names == recovery.feature_names == feature_names()

    ds = _dataset(n_transactions=400)
    fm = build_feature_matrix(ds)
    row = fm.X[0]
    tid = fm.transaction_external_ids[0]
    assert 0.0 <= recovery.predict(row, tid).recovery_probability <= 1.0
    assert 0.0 <= risk.predict(row, tid).risk_score <= 1.0


def test_load_missing_artifact_raises(tmp_path):
    with pytest.raises(ModelArtifactError):
        RiskModel.load(tmp_path / "does_not_exist.joblib")


def test_load_wrong_type_raises(tmp_path):
    rep = train_models(
        TrainingConfig(
            dataset_config=SyntheticDataConfig(n_transactions=400, seed=3),
            artifact_dir=str(tmp_path / "a"),
            save_artifacts=True,
        )
    )
    with pytest.raises(ModelArtifactError):
        RecoveryModel.load(rep.risk_artifact_path, expected_type="recovery")


# ---------------------------------------------------------------------------
# Basic evaluation
# ---------------------------------------------------------------------------

def test_report_contains_required_metrics():
    rep = _small_training()
    for m in (rep.risk, rep.recovery):
        for name in (
            "accuracy", "precision", "recall", "f1", "roc_auc",
            "brier_score", "confusion_matrix",
        ):
            assert getattr(m, name) is not None
        cm = m.confusion_matrix
        assert len(cm) == 2 and all(len(r) == 2 for r in cm)
        assert 0.0 <= m.roc_auc <= 1.0
