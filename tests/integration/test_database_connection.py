"""Integration tests against the RazorRecover PostgreSQL database."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text

from src.razor_recover.config import get_settings

EXPECTED_TABLES = {
    "alembic_version",
    "audit_logs",
    "customers",
    "merchants",
    "policies",
    "recovery_attempts",
    "recovery_decisions",
    "transactions",
}


def test_postgres_connection(postgres_engine):
    with postgres_engine.connect() as connection:
        result = connection.execute(text("SELECT current_database(), current_user"))
        database_name, database_user = result.one()

    assert database_name == "razorrecover"
    assert database_user == "razor"


def test_expected_tables_exist(postgres_engine):
    table_names = set(inspect(postgres_engine).get_table_names())
    assert EXPECTED_TABLES.issubset(table_names)


def test_alembic_version_is_at_head(postgres_engine):
    with postgres_engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()

    assert version is not None
    assert len(version) > 0


def test_crud_round_trip_on_postgres(postgres_session):
    from src.razor_recover.db.models.customer import Customer
    from src.razor_recover.db.models.merchant import Merchant
    from src.razor_recover.db.models.transaction import Transaction

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    merchant = Merchant(external_id=f"int-merchant-{suffix}", name="Integration Merchant")
    customer = Customer(external_id=f"int-customer-{suffix}", name="Integration Customer")
    postgres_session.add_all([merchant, customer])
    postgres_session.flush()

    transaction = Transaction(
        external_id=f"int-tx-{suffix}",
        customer_id=customer.id,
        merchant_id=merchant.id,
        amount=Decimal("99.99"),
        currency="USD",
        status="failed",
    )
    postgres_session.add(transaction)
    postgres_session.commit()

    loaded = postgres_session.get(Transaction, transaction.id)
    assert loaded is not None
    assert loaded.amount == Decimal("99.99")
    assert loaded.customer.external_id == customer.external_id

    postgres_session.delete(transaction)
    postgres_session.delete(customer)
    postgres_session.delete(merchant)
    postgres_session.commit()


def test_settings_database_url_targets_razorrecover():
    settings = get_settings()
    assert "razorrecover" in settings.database_url
    assert ":5433/" in settings.database_url
