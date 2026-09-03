"""Unit tests for database exception mapping."""

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from src.razor_recover.core.exceptions import (
    ConflictError,
    DatabaseError,
    DatabaseUnavailableError,
    NotFoundError,
    map_sqlalchemy_error,
    to_http_error,
)


def test_map_integrity_error_to_conflict():
    original = IntegrityError("insert", {}, Exception("duplicate key"))
    mapped = map_sqlalchemy_error(original)
    assert isinstance(mapped, ConflictError)


def test_map_operational_error_to_unavailable():
    original = OperationalError("select", {}, Exception("connection refused"))
    mapped = map_sqlalchemy_error(original)
    assert isinstance(mapped, DatabaseUnavailableError)


def test_map_generic_sqlalchemy_error():
    original = SQLAlchemyError("generic failure")
    mapped = map_sqlalchemy_error(original)
    assert isinstance(mapped, DatabaseError)


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (NotFoundError("missing"), status.HTTP_404_NOT_FOUND),
        (ConflictError("duplicate"), status.HTTP_409_CONFLICT),
        (DatabaseUnavailableError("down"), status.HTTP_503_SERVICE_UNAVAILABLE),
        (DatabaseError("unknown"), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
)
def test_to_http_error_status_codes(exc, expected_status):
    http_exc = to_http_error(exc)
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == expected_status
