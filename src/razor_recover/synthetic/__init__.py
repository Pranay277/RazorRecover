"""Synthetic data generation for the RazorRecover MVP dataset.

Provides configurable, reproducible generation separate from persistence.
"""

from razor_recover.synthetic.config import SyntheticDataConfig
from razor_recover.synthetic.dataset import generate_dataset
from razor_recover.synthetic.persistence import write_dataset
from razor_recover.synthetic.schemas import SyntheticDataset

__all__ = [
    "SyntheticDataConfig",
    "SyntheticDataset",
    "generate_dataset",
    "write_dataset",
]
