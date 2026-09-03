"""Configuration for synthetic data generation.

Kept intentionally minimal and type-safe. All sizes are configurable with
sensible development defaults; no hardcoded "10,000 records" assumptions.
"""

from pydantic import BaseModel, Field


class SyntheticDataConfig(BaseModel):
    """Controls the size and reproducibility of a generated dataset."""

    n_merchants: int = Field(default=20, ge=1, description="Number of merchants")
    n_customers: int = Field(default=100, ge=1, description="Number of customers")
    n_transactions: int = Field(
        default=1000, ge=1, description="Number of transactions"
    )
    seed: int = Field(default=42, description="Random seed for reproducibility")
