"""Shared constants and source pools for synthetic data generation.

The failure/resolution categories listed here reflect the realistic set a
payment recovery system reasons about. All generators draw from these pools.
"""

# Failure categories the recovery pipeline reasons about.
FAILURE_CATEGORIES: list[str] = [
    "insufficient_funds",
    "bank_declined",
    "authentication_failed",
    "network_timeout",
    "gateway_error",
    "expired_card",
    "limit_exceeded",
    "unknown",
]

# Relative weights for the failure categories (must align with category list,
# in the same order above). Non-uniform => more realistic distribution.
FAILURE_WEIGHTS: list[float] = [
    0.25,  # insufficient_funds
    0.20,  # bank_declined
    0.15,  # authentication_failed
    0.10,  # network_timeout
    0.12,  # gateway_error
    0.08,  # expired_card
    0.07,  # limit_exceeded
    0.03,  # unknown
]

# Human-readable explanation templates keyed by failure category.
FAILURE_REASONS: dict[str, str] = {
    "insufficient_funds": "Account balance below transaction amount",
    "bank_declined": "Bank declined the payment",
    "authentication_failed": "Customer authentication failed or timed out",
    "network_timeout": "Request timed out on the payment network",
    "gateway_error": "Payment gateway returned an error",
    "expired_card": "The payment card has expired",
    "limit_exceeded": "Daily or per-transaction limit exceeded",
    "unknown": "Unclassified failure",
}

# Payment methods used by customers.
PAYMENT_METHODS: list[str] = [
    "card",
    "bank_transfer",
    "wallet",
    "upi",
]

# Payment gateways / banks involved in processing.
GATEWAYS: list[str] = [
    "stripe",
    "adyen",
    "braintree",
    "razorpay",
    "paypal",
    "worldpay",
    "chase",
    "barclays",
]

# Currencies the system may process.
CURRENCIES: list[str] = ["USD", "EUR", "GBP", "INR"]

# Transaction lifecycle statuses.
TRANSACTION_STATUSES: list[str] = ["failed", "pending", "recovered", "abandoned"]

# Recovery actions the policy engine may authorize.
RECOVERY_ACTIONS: list[str] = [
    "retry",
    "switch_payment_method",
    "dunning_email",
    "request_new_card",
    "hold_drop",
]

# Decision outcomes.
DECISION_OUTCOMES: list[str] = ["authorized", "denied"]

# Recovery attempt lifecycle statuses.
ATTEMPT_STATUSES: list[str] = ["pending", "running", "success", "failed"]

# --- Customer / merchant pools (for plausible names) ---
CUSTOMER_FIRST_NAMES: list[str] = [
    "Aarav", "Maya", "Liam", "Sofia", "Noah", "Zara", "Ethan", "Priya",
    "Lucas", "Ana", "Mateo", "Chloe", "Ravi", "Emma", "Jonas", "Leila",
]

CUSTOMER_LAST_NAMES: list[str] = [
    "Sharma", "Patel", "Smith", "Garcia", "Kim", "Rossi", "Tanaka", "Silva",
    "Novak", "Kapoor", "Haddad", "Okafor", "Mueller", "Costa", "Nguyen", "Ali",
]

DOMAINS: list[str] = ["example.com", "mail.test", "inbox.dev", "corp.net"]

MERCHANT_NAMES: list[str] = [
    "Nimbus Retail", "Cloudline Goods", "Bluepeak Mart", "Evergreen Outfitters",
    "Vertex Electronics", "Lumina Home", "Core & Co", "Trailhead Supply",
    "Solstice Travel", "Pine & Pearl",
]

INDUSTRIES: list[str] = [
    "electronics", "fashion", "groceries", "travel", "subscriptions",
    "telecom", "fitness", "entertainment",
]
