"""RecoveryAttempt model – the execution of an authorized recovery action."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from razor_recover.db.models.base import Base, TimestampMixin


class RecoveryAttempt(TimestampMixin, Base):
    """A single attempt to execute an authorized recovery action."""

    __tablename__ = "recovery_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("recovery_decisions.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempt_type: Mapped[str] = mapped_column(String(64), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    transaction = relationship("Transaction", back_populates="recovery_attempts")
    decision = relationship("RecoveryDecision", back_populates="recovery_attempts")
