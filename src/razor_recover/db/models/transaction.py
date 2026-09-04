"""Transaction model – a payment that failed and may be recovered."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.razor_recover.db.models.base import Base, TimestampMixin


class Transaction(TimestampMixin, Base):
    """A payment transaction subject to recovery."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"), index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(32), default="failed", index=True)

    failure_code: Mapped[str | None] = mapped_column(String(128), index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payment_method: Mapped[str | None] = mapped_column(String(64), index=True)
    gateway: Mapped[str | None] = mapped_column(String(128), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)

    customer = relationship("Customer", back_populates="transactions")
    merchant = relationship("Merchant", back_populates="transactions")

    decisions = relationship("RecoveryDecision", back_populates="transaction")
    recovery_attempts = relationship("RecoveryAttempt", back_populates="transaction")
