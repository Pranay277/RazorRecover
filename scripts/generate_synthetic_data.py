#!/usr/bin/env python
"""Generate and persist a synthetic RazorRecover dataset.

Runs with sensible development defaults when invoked without arguments:

    python scripts/generate_synthetic_data.py

All parameters are configurable via CLI flags. Adding ``--dry-run`` produces
the dataset in memory without touching the database.

This script belongs to the scripts/ directory (not packaged), so it adds the
project ``src`` directory to ``sys.path`` when run directly.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and persist a synthetic RazorRecover dataset."
    )
    parser.add_argument(
        "--merchants",
        type=int,
        default=20,
        help="Number of merchants (default: 20)",
    )
    parser.add_argument(
        "--customers",
        type=int,
        default=100,
        help="Number of customers (default: 100)",
    )
    parser.add_argument(
        "--transactions",
        type=int,
        default=1000,
        help="Number of transactions (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible output (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate only in memory; do not write to the database",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from razor_recover.core.database import SessionLocal
    from razor_recover.core.logger import get_logger
    from razor_recover.synthetic import (
        SyntheticDataConfig,
        generate_dataset,
        write_dataset,
    )

    logger = get_logger("cli.generate")

    config = SyntheticDataConfig(
        n_merchants=args.merchants,
        n_customers=args.customers,
        n_transactions=args.transactions,
        seed=args.seed,
    )

    logger.info(
        "Generating dataset: merchants=%d customers=%d transactions=%d seed=%d",
        config.n_merchants,
        config.n_customers,
        config.n_transactions,
        config.seed,
    )
    dataset = generate_dataset(config)
    logger.info(
        "Generated %d entities (decisions=%d attempts=%d)",
        dataset.total_entities,
        len(dataset.decisions),
        len(dataset.recovery_attempts),
    )

    if args.dry_run:
        logger.info("Dry run: skipping database write")
        return 0

    with SessionLocal() as session:
        written = write_dataset(session, dataset, clear_existing=True)
        session.commit()
        logger.info("Wrote %d records to the database", written)

    return 0


if __name__ == "__main__":
    sys.exit(main())
