from __future__ import annotations

import json
import re
import uuid
from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import (
    Citation,
    ConfidenceLevel,
    HumanReviewReason,
    QueryResponse,
    RoutingDestination,
)
from prodrag.prompts import ANSWER_PROMPT
from prodrag.retrieval.confidence import ConfidenceGrader
from prodrag.triage import QuestionTriage

_CITATION_MARKER_RE = re.compile(r"(?:\[|\u3010)\s*(S\d+)\s*(?:\]|\u3011)", re.IGNORECASE)


class GroundedAnswerService:
    def __init__(
        self,
        settings: Settings,
        chat_model: BaseChatModel,
        confidence_grader: ConfidenceGrader,
    ) -> None:
        self.settings = settings
        self.confidence_grader = confidence_grader
        self._chain = ANSWER_PROMPT | chat_model | StrOutputParser()

    def answer(
        self,
        question: str,
        candidates: Sequence[RetrievedCandidate],
        *,
        request_id: str | None = None,
        question_triage: QuestionTriage,
    ) -> QueryResponse:
        request_id = request_id or str(uuid.uuid4())
        if question_triage.sensitive_data_types:
            return QueryResponse(
                request_id=request_id,
                category=question_triage.category,
                confidence=ConfidenceLevel.LOW,
                requires_human_review=True,
                routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                answered=False,
                answer=(
                    "The safety classifier detected sensitive data, so no automatic answer "
                    "was generated. Human review is required; route this ticket to the "
                    "secure customer-support queue."
                ),
                escalation_reasons=[HumanReviewReason.SENSITIVE_DATA],
                sensitive_data_types=list(question_triage.sensitive_data_types),
            )

        confidence = self.confidence_grader.grade(candidates)
        if not candidates:
            return QueryResponse(
                request_id=request_id,
                category=question_triage.category,
                confidence=ConfidenceLevel.LOW,
                requires_human_review=True,
                routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                answered=False,
                answer=(
                    "The indexed documentation does not contain enough relevant evidence to "
                    "answer safely. Human review is required; route this ticket to customer "
                    "support."
                ),
                escalation_reasons=[HumanReviewReason.INSUFFICIENT_CONTEXT],
            )
        if confidence == ConfidenceLevel.LOW:
            return QueryResponse(
                request_id=request_id,
                category=question_triage.category,
                confidence=confidence,
                requires_human_review=True,
                routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                answered=False,
                answer=(
                    "Retrieval confidence is low, so no automatic answer was generated. "
                    "Human review is required; route this ticket to customer support."
                ),
                escalation_reasons=[HumanReviewReason.LOW_CONFIDENCE],
            )

        source_payload: list[dict[str, str]] = []
        citations: list[Citation] = []
        remaining = self.settings.context_char_budget
        for candidate in candidates:
            if remaining <= 0:
                break
            metadata = candidate.document.metadata
            content = candidate.document.page_content[:remaining]
            if not content:
                continue
            source_id = f"S{len(source_payload) + 1}"
            source_payload.append(
                {
                    "source_id": source_id,
                    "title": str(metadata.get("title", "Untitled")),
                    "section": str(metadata.get("section", "Document")),
                    "content": content,
                }
            )
            citations.append(
                Citation(
                    source_id=source_id,
                    document_id=str(metadata.get("document_id", "")),
                    title=str(metadata.get("title", "Untitled")),
                    section=str(metadata.get("section", "Document")),
                    source_name=str(metadata.get("source_name", "unknown")),
                    relevance_score=round(candidate.final_score, 6),
                )
            )
            remaining -= len(content)

        invoke_payload = {
            "question": question,
            "sources": json.dumps(source_payload, ensure_ascii=False),
        }
        last_error: Exception | None = None
        for _ in range(self.settings.model_retry_attempts):
            try:
                raw_answer = self._chain.invoke(invoke_payload).strip()
                break
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError("Answer generation failed after retries") from last_error
        if raw_answer == "NOT_FOUND" or not raw_answer:
            return QueryResponse(
                request_id=request_id,
                category=question_triage.category,
                confidence=ConfidenceLevel.LOW,
                requires_human_review=True,
                routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                answered=False,
                answer=(
                    "The retrieved sources do not contain enough grounded evidence to answer "
                    "safely. Human review is required; route this ticket to customer support."
                ),
                escalation_reasons=[HumanReviewReason.INSUFFICIENT_CONTEXT],
            )
        # OCI-hosted models may add spaces or use full-width brackets around source IDs.
        # Canonicalize only valid source-marker shapes before checking them against metadata.
        raw_answer = _CITATION_MARKER_RE.sub(
            lambda match: f"[{match.group(1).upper()}]", raw_answer
        )
        cited_source_ids = set(re.findall(r"\[(S\d+)\]", raw_answer))
        used_citations = [
            citation for citation in citations if citation.source_id in cited_source_ids
        ]
        if not used_citations:
            return QueryResponse(
                request_id=request_id,
                category=question_triage.category,
                confidence=ConfidenceLevel.LOW,
                requires_human_review=True,
                routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                answered=False,
                answer=(
                    "The generated answer did not include verifiable source citations. Human "
                    "review is required; route this ticket to customer support."
                ),
                escalation_reasons=[HumanReviewReason.MISSING_CITATIONS],
            )
        return QueryResponse(
            request_id=request_id,
            category=question_triage.category,
            confidence=confidence,
            requires_human_review=question_triage.policy_review_required,
            routing_destination=(
                RoutingDestination.CUSTOMER_SUPPORT
                if question_triage.policy_review_required
                else None
            ),
            answered=True,
            answer=raw_answer,
            escalation_reasons=(
                [HumanReviewReason.POLICY_RULE]
                if question_triage.policy_review_required
                else []
            ),
            citations=used_citations,
        )
