"""Application exceptions and clean mapping of database errors."""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError


class DatabaseError(Exception):
    """Base exception for database-related failures."""


class NotFoundError(DatabaseError):
    """Raised when a requested record does not exist."""


class ConflictError(DatabaseError):
    """Raised when an operation violates a uniqueness/constraint rule."""


class DatabaseUnavailableError(DatabaseError):
    """Raised when the database cannot be reached."""


def map_sqlalchemy_error(exc: SQLAlchemyError) -> DatabaseError:
    """Translate a SQLAlchemy exception into a domain exception."""
    if isinstance(exc, IntegrityError):
        return ConflictError(str(exc.__cause__))
    if isinstance(exc, OperationalError):
        return DatabaseUnavailableError(str(exc))
    return DatabaseError(str(exc))


def to_http_error(exc: DatabaseError) -> HTTPException:
    """Convert a domain database error into an HTTP response."""
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, DatabaseUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
    )


__all__ = [
    "ConflictError",
    "DatabaseError",
    "DatabaseUnavailableError",
    "NotFoundError",
    "map_sqlalchemy_error",
    "to_http_error",
]
