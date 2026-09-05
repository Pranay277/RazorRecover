"""Policy model – deterministic recovery policies enforced by the shield."""

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from razor_recover.db.models.base import Base, TimestampMixin


class Policy(TimestampMixin, Base):
    """A deterministic rule/policy used by the policy engine."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(default=100)

    decisions = relationship("RecoveryDecision", back_populates="policy")
