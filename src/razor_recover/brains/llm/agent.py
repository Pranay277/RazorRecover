"""The AI decision agent: turns context into a structured recovery RECOMMENDATION.

The agent consumes ML scores and RAG knowledge but NEVER executes any action,
writes to any store, or mutates state. It returns a validated
:class:`AgentDecision` (a recommendation) that the Policy Engine will later
authorize and the Execution layer will perform.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from razor_recover.brains.llm.exceptions import (
    InvalidDecisionError,
    LLMError,
    LLMProviderError,
)
from razor_recover.brains.llm.prompts import build_messages
from razor_recover.brains.llm.providers import LLMProvider
from razor_recover.brains.llm.schemas import (
    AgentDecision,
    DecisionRequest,
)
from razor_recover.core.logger import get_logger

logger: logging.Logger = get_logger("brains.llm.agent")


def extract_json(text: str) -> dict[str, Any]:
    """Robustly extract a JSON object from an LLM response.

    Handles whole-JSON, fenced (```json) and text-with-trailing-JSON cases.
    Raises :class:`InvalidDecisionError` if no valid JSON object is found.
    """
    if not text or not text.strip():
        raise InvalidDecisionError("LLM returned an empty response.")

    stripped = text.strip()
    # Whole-string JSON fast path.
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences if present.
    fenced = re.sub(r"```(?:json)?\s*", "", stripped, flags=re.IGNORECASE).strip()
    fenced = re.sub(r"\s*```", "", fenced).strip()
    try:
        obj = json.loads(fenced)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Find the first balanced {...}  region.
    start = fenced.find("{")
    end = fenced.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = fenced[start : end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise InvalidDecisionError("Could not extract a valid JSON object from the LLM response.")


def parse_decision(
    raw: str,
    transaction_external_id: str,
) -> AgentDecision:
    """Parse + validate provider output into a :class:`AgentDecision`.

    Raises :class:`InvalidDecisionError` on malformed JSON, missing/invalid
    fields, invalid action, or out-of-range scores.
    """
    obj = extract_json(raw)
    # The decision is scoped to a single request; always bind the correct id.
    obj["transaction_external_id"] = transaction_external_id
    try:
        return AgentDecision.model_validate(obj)
    except ValidationError as exc:
        raise InvalidDecisionError(f"LLM output failed validation: {exc}") from exc


class DecisionAgent:
    """Orchestrates generation, validation and safe failure of a decision."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def decide(self, request: DecisionRequest) -> AgentDecision:
        """Produce a validated recovery recommendation from the request."""
        try:
            system, user = build_messages(request)
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            raw = self.provider.complete(messages)
        except LLMError:
            raise  # controlled failure; never fabricate a decision
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected provider failure")
            raise LLMProviderError(f"Provider failure during decision: {exc}") from exc

        decision = parse_decision(raw, request.transaction.external_id)
        logger.info(
            "Agent recommended %s (confidence=%.2f, review=%s) for %s",
            decision.action.value,
            decision.confidence,
            decision.requires_policy_review,
            request.transaction.external_id,
        )
        return decision
