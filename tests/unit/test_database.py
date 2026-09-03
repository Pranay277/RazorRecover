"""Unit tests for database engine, session management, and metadata."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from src.razor_recover.core.database import Base, get_db
from src.razor_recover.db.models.customer import Customer
from src.razor_recover.db.models.merchant import Merchant
from src.razor_recover.db.models.transaction import Transaction


EXPECTED_TABLES = {
    "audit_logs",
    "customers",
    "merchants",
    "policies",
    "recovery_attempts",
    "recovery_decisions",
    "transactions",
}


def test_base_metadata_registers_all_domain_tables():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_sqlite_engine_creates_expected_tables(sqlite_engine):
    table_names = set(inspect(sqlite_engine).get_table_names())
    assert EXPECTED_TABLES.issubset(table_names)


def test_get_db_commits_and_closes(get_db_session):
    gen = get_db_session()
    session = next(gen)
    suffix = datetime.now(timezone.utc).strftime("%f")
    session.add(Merchant(external_id=f"m-{suffix}", name="Acme Corp"))
    with pytest.raises(StopIteration):
        next(gen)

    verify_gen = get_db_session()
    verify_session = next(verify_gen)
    loaded = verify_session.query(Merchant).filter_by(external_id=f"m-{suffix}").one()
    assert loaded.name == "Acme Corp"
    with pytest.raises(StopIteration):
        next(verify_gen)


def test_get_db_rolls_back_on_error(get_db_session):
    suffix = datetime.now(timezone.utc).strftime("%f")
    gen = get_db_session()
    session = next(gen)
    session.add(Merchant(external_id=f"m-rollback-{suffix}", name="Rollback Inc"))
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("simulated failure"))

    verify_gen = get_db_session()
    verify_session = next(verify_gen)
    assert (
        verify_session.query(Merchant).filter_by(external_id=f"m-rollback-{suffix}").first()
        is None
    )
    with pytest.raises(StopIteration):
        next(verify_gen)


def test_transaction_relationships(postgres_session_isolated):
    suffix = datetime.now(timezone.utc).strftime("%f")
    customer = Customer(
        external_id=f"c-{suffix}",
        name="Jane Doe",
        email="jane@example.com",
    )
    merchant = Merchant(external_id=f"m-{suffix}", name="Shop LLC")
    postgres_session_isolated.add_all([customer, merchant])
    postgres_session_isolated.flush()

    transaction = Transaction(
        external_id=f"tx-{suffix}",
        customer_id=customer.id,
        merchant_id=merchant.id,
        amount=Decimal("42.50"),
        currency="USD",
        status="failed",
        failure_code="insufficient_funds",
        attempted_at=datetime.now(timezone.utc),
    )
    postgres_session_isolated.add(transaction)
    postgres_session_isolated.flush()

    loaded = postgres_session_isolated.get(Transaction, transaction.id)
    assert loaded.customer.name == "Jane Doe"
    assert loaded.merchant.name == "Shop LLC"


def test_get_db_is_generator():
    assert hasattr(get_db(), "__iter__")
