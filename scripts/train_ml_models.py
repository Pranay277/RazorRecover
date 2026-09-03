"""CLI entry point for training the ML models on a synthetic dataset.

Usage:
    python scripts/train_ml_models.py \
        --merchants 20 --customers 100 --transactions 5000 --seed 7 \
        --test-size 0.25 --artifact-dir models

Prints a summary of the trained models and saves joblib artifacts
(``risk_model.joblib`` and ``recovery_model.joblib``) under ``models/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the project ``src`` tree is importable when run as a plain script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.razor_recover.brains.ml.training import (
    RECOVERY_ARTIFACT_NAME,
    RISK_ARTIFACT_NAME,
    TrainingConfig,
    train_models,
)
from src.razor_recover.core.logger import configure_logging
from src.razor_recover.synthetic import SyntheticDataConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train RazorRecover ML models.")
    p.add_argument("--merchants", type=int, default=20)
    p.add_argument("--customers", type=int, default=100)
    p.add_argument("--transactions", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test-size", type=float, default=0.25)
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--max-iter", type=int, default=1000)
    p.add_argument("--artifact-dir", type=str, default=None,
                   help="Directory for model artifacts (default: ./models).")
    p.add_argument("--no-save", action="store_true", help="Train but do not write artifacts.")
    p.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)

    dataset_config = SyntheticDataConfig(
        n_merchants=args.merchants,
        n_customers=args.customers,
        n_transactions=args.transactions,
        seed=args.seed,
    )
    config = TrainingConfig(
        dataset_config=dataset_config,
        test_size=args.test_size,
        random_state=args.random_state,
        max_iter=args.max_iter,
        artifact_dir=args.artifact_dir,
        save_artifacts=not args.no_save,
    )

    report = train_models(config)

    if args.json:
        print(json.dumps(report.model_dump(), indent=2, default=str))
        return 0

    print("\n=== ML Training Summary ===")
    print(f"seed={report.seed}  samples={report.n_samples}  "
          f"train={report.n_train}  test={report.n_test}  features={report.n_features}")
    print("\n--- Risk model ---")
    print(f"  accuracy={report.risk.accuracy} precision={report.risk.precision} "
          f"recall={report.risk.recall} f1={report.risk.f1}")
    print(f"  roc_auc={report.risk.roc_auc} brier={report.risk.brier_score} "
          f"log_loss={report.risk.log_loss}")
    print(f"  confusion_matrix={report.risk.confusion_matrix}")
    print(f"  artifact={report.risk_artifact_path or '(not saved)'}")
    print("\n--- Recovery model ---")
    print(f"  accuracy={report.recovery.accuracy} precision={report.recovery.precision} "
          f"recall={report.recovery.recall} f1={report.recovery.f1}")
    print(f"  roc_auc={report.recovery.roc_auc} brier={report.recovery.brier_score} "
          f"log_loss={report.recovery.log_loss}")
    print(f"  confusion_matrix={report.recovery.confusion_matrix}")
    print(f"  artifact={report.recovery_artifact_path or '(not saved)'}")
    print("\nExcluded leaked fields:", report.excluded_leaked_fields)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
