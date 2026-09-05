"""Merchant model – the business that issued the payment request."""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from razor_recover.db.models.base import Base, TimestampMixin


class Merchant(TimestampMixin, Base):
    """A merchant who submits payments that occasionally fail."""

    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)

    transactions = relationship("Transaction", back_populates="merchant")
