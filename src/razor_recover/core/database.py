"""Centralized database configuration, engine, session and Base.

This is the single source of truth for how the application connects to
PostgreSQL. All models must inherit from ``Base`` defined here, and all
session access must go through ``get_db`` or the ``SessionLocal`` factory
so that the persistence layer stays consistent and independently testable.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.razor_recover.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session, ensuring it is always closed.

    Intended to be used as a FastAPI dependency and as a context manager
    in non-HTTP contexts (scripts, workers, tests).
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
