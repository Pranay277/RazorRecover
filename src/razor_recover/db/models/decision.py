"""RecoveryDecision model – the outcome of ML + RAG + LLM + policy shield."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from razor_recover.db.models.base import Base, TimestampMixin


class RecoveryDecision(TimestampMixin, Base):
    """A single decision recommending (or rejecting) a recovery action."""

    __tablename__ = "recovery_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(32), default="authorized")
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("policies.id", ondelete="SET NULL"), index=True
    )
    policy_version: Mapped[int | None] = mapped_column(Integer)

    rationale: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    transaction = relationship("Transaction", back_populates="decisions")
    policy = relationship("Policy", back_populates="decisions")
    recovery_attempts = relationship("RecoveryAttempt", back_populates="decision")
