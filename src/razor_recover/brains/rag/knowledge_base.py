"""Synthetic/demo knowledge base for the RazorRecover RAG layer.

IMPORTANT: These are NOT real Razorpay policies. Every document is clearly
marked as a synthetic demo policy written for the RazorRecover project, used to
exercise the RAG pipeline. Most documents apply globally (``merchant_scope`` is
None); a few are scoped to demo merchants so merchant filtering can be tested.

Documents are grouped by ``category`` so the retriever can surface useful
metadata (source/category/scope) alongside content.
"""

from __future__ import annotations

from src.razor_recover.brains.rag.exceptions import DocumentError
from src.razor_recover.brains.rag.schemas import KnowledgeDocument

# Explicit, machine-readable marker used in every document.
DEMO_DISCLAIMER = (
    "SYNTHETIC DEMO POLICY for RazorRecover. Not an actual Razorpay policy."
)


def _demo(title: str, category: str, content: str, **kw) -> KnowledgeDocument:
    base = {
        "id": kw.pop("id", None),
        "category": category,
        "title": title,
        "source": "synthetic-demo",
    }
    # Auto-generate a stable id from the title if not supplied.
    if base["id"] is None:
        import re

        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        base["id"] = f"{category}::{slug}"
    return KnowledgeDocument(
        content=f"{DEMO_DISCLAIMER}. {content}",
        **base,
        **kw,
    )


DEMO_KNOWLEDGE_DOCUMENTS: list[KnowledgeDocument] = [
    # ---- merchant recovery policies ----
    _demo(
        "Global retry policy for failed card payments",
        "merchant_recovery_policy",
        "Card payment failures should be retried a maximum of three times within 48 hours "
        "before escalating to manual review. Do not retry more than once per 15 minutes.",
    ),
    _demo(
        "Nimbus Retail high-volume recovery policy",
        "merchant_recovery_policy",
        "For Nimbus Retail, failed payments above 5000 should be escalated to manual "
        "review after two retries instead of the usual three, because of the ticket size.",
        merchant_scope="Nimbus Retail",
    ),
    _demo(
        "Vertex Electronics refund vs retry guidance",
        "merchant_recovery_policy",
        "For Vertex Electronics, prefer issuing a fresh payment link over blind retries for "
        "authentication failures, reducing repeated card decline risk.",
        merchant_scope="Vertex Electronics",
    ),

    # ---- retry limits ----
    _demo(
        "Retry limit by failure category",
        "retry_limits",
        "Network timeouts and gateway errors may be retried up to three times. "
        "Insufficient funds and bank declines may be retried up to two times. "
        "Unknown failures are always single-shot and require manual review.",
    ),
    _demo(
        "Per-customer daily retry cap",
        "retry_limits",
        "No more than four recovery attempts should target the same customer within a "
        "single calendar day regardless of payment count, to avoid bad customer experience.",
    ),

    # ---- customer communication rules ----
    _demo(
        "Customer notification thresholds",
        "customer_communication",
        "Notify customers before the first retry for high-value payments, after the first "
        "failure for subscription renewals, and only after two failed attempts for other "
        "low-value payments.",
    ),
    _demo(
        "Do-not-contact window",
        "customer_communication",
        "Never initiate dunning emails or reminders between 22:00 and 08:00 in the "
        "customer's local timezone.",
    ),

    # ---- payment failure handling guidance ----
    _demo(
        "Insufficient funds handling",
        "payment_failure_handling",
        "For insufficient funds, do not retry immediately. Send a dunning email and retry "
        "only after the account is replenished, or within 24 hours.",
    ),
    _demo(
        "Expired card handling",
        "payment_failure_handling",
        "For expired cards, trigger a card-revalidation flow requesting an updated payment "
        "method before any further retry attempts.",
    ),

    # ---- risk / recovery guidelines ----
    _demo(
        "Recovery risk scoring guidance",
        "risk_guidelines",
        "Payments with high recovery risk score should be routed to dunning or manual "
        "review rather than automated retries, to reduce repeat-decline cost.",
    ),
    _demo(
        "High-value payment recovery priority",
        "risk_guidelines",
        "Prioritize manual recovery effort by expected value: high amount and high "
        "recovery probability first.",
    ),

    # ---- escalation / manual review ----
    _demo(
        "Manual review escalation triggers",
        "escalation_manual_review",
        "Escalate to manual review when a payment fails three times, when fraud indicators "
        "are present, or when the amount exceeds the merchant's manual-review threshold.",
    ),
    _demo(
        "Manual review SLA",
        "escalation_manual_review",
        "Manual review cases must be actioned by an operator within 24 hours of escalation.",
    ),

    # ---- compliance / safety ----
    _demo(
        "Regulatory hold on retries",
        "compliance_safety",
        "Do not attempt recovery retries while a payment is under regulatory hold or "
        "flagged for compliance investigation.",
    ),
    _demo(
        "Data-privacy constraints on customer contact",
        "compliance_safety",
        "Only contact customers using approved channels and retain the minimum personal "
        "data required. Do not store responses outside the sanctioned data store.",
    ),
]


def load_documents() -> list[KnowledgeDocument]:
    """Return the demo knowledge-base documents, validating each one."""
    docs = [KnowledgeDocument.model_validate(d) for d in DEMO_KNOWLEDGE_DOCUMENTS]
    ids = [d.id for d in docs]
    if len(ids) != len(set(ids)):
        raise DocumentError("Knowledge base contains duplicate document ids.")
    return docs
