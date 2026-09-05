"""Merchant policy resolution for the workflow.

An injectable provider decides what :class:`MerchantPolicy` applies to a
transaction. The default implementation builds a deterministic RazorRecover demo
policy from ``ShieldConfig`` demo defaults (clearly not real Razorpay limits).
Providers can be swapped in tests or for DB-backed policy later.
"""

from __future__ import annotations

from typing import Protocol

from razor_recover.shield.schemas import MerchantPolicy, ShieldConfig


class MerchantPolicyProvider(Protocol):
    """Resolves the applicable merchant policy for a transaction."""

    def get_policy(self, merchant_external_id: str | None) -> MerchantPolicy | None: ...


class DefaultMerchantPolicyProvider:
    """Builds a deterministic demo policy (RazorRecover demo values)."""

    def __init__(self, config: ShieldConfig | None = None) -> None:
        self.config = config or ShieldConfig()

    def get_policy(self, merchant_external_id: str | None) -> MerchantPolicy | None:
        if not merchant_external_id:
            return None
        # Demo policy using engine-level configurable defaults. In production
        # this would load a stored per-merchant policy from the database.
        return MerchantPolicy(
            merchant_external_id=merchant_external_id,
            retry_enabled=True,
            max_retries=self.config.default_max_retries,
            max_risk_score=self.config.default_max_risk_score,
            min_recovery_probability=self.config.default_min_recovery_probability,
            high_value_threshold=self.config.default_high_value_threshold,
            customer_notifications_enabled=True,
            disallowed_actions=[],
            policy_version=self.config.policy_version,
        )


__all__ = ["MerchantPolicyProvider", "DefaultMerchantPolicyProvider"]
