"""Reusable FastAPI dependencies."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.razor_recover.core.database import get_db


def db_session() -> Generator[Session, None, None]:
    """Dependency that provides a database session to request handlers."""
    yield from get_db()


__all__ = ["db_session"]
