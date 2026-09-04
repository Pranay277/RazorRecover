"""Centralized exceptions for the Policy / Safety Engine (shield).

The policy engine is the deterministic safety boundary. Exceptions raised here
represent invalid usage (not data conditions - missing data is handled as
fail-closed ``REVIEW``/``BLOCK`` decisions, not exceptions) and unexpected
failures that the engine maps to ``BLOCK``.
"""

from __future__ import annotations


class PolicyError(Exception):
    """Base exception for the Policy / Safety Engine."""


class InvalidPolicyContextError(PolicyError):
    """The provided evaluation context is malformed/wrong-typed."""


class PolicyEvaluationError(PolicyError):
    """An unexpected failure occurred while evaluating rules."""


class UnknownRuleError(PolicyError):
    """A rule name was not found in the engine's rule set."""


__all__ = [
    "PolicyError",
    "InvalidPolicyContextError",
    "PolicyEvaluationError",
    "UnknownRuleError",
]
