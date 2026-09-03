"""Application logging configuration.

Provides a single ``get_logger`` entry point so all modules log through a
consistent, reusable logger (including the synthetic data generator and
persistence layer).
"""

import logging
from typing import Any

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root application logger once."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger("razor_recover")
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger under the ``razor_recover`` namespace."""
    configure_logging()
    return logging.getLogger(f"razor_recover.{name}")


__all__ = ["configure_logging", "get_logger"]
