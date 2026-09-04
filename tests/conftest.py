"""Shared pytest fixtures for RazorRecover tests."""

import pytest
from sqlalchemy import BigInteger, create_engine, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from src.razor_recover.config import get_settings
from src.razor_recover.core.database import Base, get_db
from src.razor_recover.db import models  # noqa: F401 - register ORM models


# SQLite only auto-increments INTEGER PRIMARY KEY (the rowid alias); our models
# use BigInteger PKs for PostgreSQL. Compile BigInteger as INTEGER on SQLite so
# in-memory unit/integration tests get functioning autoincrement PKs.
@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine for fast, isolated unit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sqlite_session(sqlite_engine) -> Session:
    """Database session backed by in-memory SQLite."""
    session_factory = sessionmaker(
        bind=sqlite_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def postgres_engine():
    """PostgreSQL engine for integration tests; skips when unavailable."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine) -> Session:
    """Database session backed by the configured PostgreSQL instance."""
    session_factory = sessionmaker(
        bind=postgres_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def postgres_session_isolated(postgres_engine) -> Session:
    """PostgreSQL session wrapped in a transaction that always rolls back."""
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def get_db_session(postgres_session_isolated):
    """Provide get_db() wired to an isolated PostgreSQL transaction."""
    connection = postgres_session_isolated.get_bind()

    def override_get_db():
        session = Session(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return override_get_db
