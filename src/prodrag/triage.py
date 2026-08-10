from __future__ import annotations

import json
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from prodrag.models import ConfidenceLevel, SensitiveDataType, TicketCategory
from prodrag.prompts import TRIAGE_PROMPT


class TriageClassificationError(RuntimeError):
    """Raised when the model cannot produce a safe, valid routing decision."""


class _TriagePayload(BaseModel):
    category: TicketCategory
    sensitive_data_types: list[SensitiveDataType] = Field(default_factory=list)
    policy_review_required: bool
    classification_confidence: ConfidenceLevel


@dataclass(frozen=True)
class QuestionTriage:
    category: TicketCategory
    sensitive_data_types: tuple[SensitiveDataType, ...]
    policy_review_required: bool
    classification_confidence: ConfidenceLevel


class TicketTriageService:
    """Use an LLM to classify a ticket before retrieval."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._chain = TRIAGE_PROMPT | chat_model | StrOutputParser()

    def inspect_question(self, question: str) -> QuestionTriage:
        try:
            raw_result = self._chain.invoke(
                {"question_json": json.dumps(question, ensure_ascii=True)}
            ).strip()
            payload = _TriagePayload.model_validate_json(_extract_json_object(raw_result))
        except Exception as exc:
            raise TriageClassificationError(
                "The LLM triage response was unavailable or invalid"
            ) from exc

        sensitive_types = tuple(
            sorted(set(payload.sensitive_data_types), key=lambda item: item.value)
        )
        return QuestionTriage(
            category=payload.category,
            sensitive_data_types=sensitive_types,
            policy_review_required=payload.policy_review_required,
            classification_confidence=payload.classification_confidence,
        )

def _extract_json_object(raw_result: str) -> str:
    start = raw_result.find("{")
    end = raw_result.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Triage output did not contain a JSON object")
    return raw_result[start : end + 1]
