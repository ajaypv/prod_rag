from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.flow import FlowCallback, emit_flow_event
from prodrag.models import (
    Citation,
    ConfidenceLevel,
    FlowStatus,
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

    def prepare_evidence(
        self, candidates: Sequence[RetrievedCandidate]
    ) -> list[RetrievedCandidate]:
        """Return the exact ranked/truncated contexts that fit in the answer prompt budget."""
        evidence: list[RetrievedCandidate] = []
        remaining = self.settings.context_char_budget
        for candidate in candidates:
            if remaining <= 0:
                break
            content = candidate.document.page_content[:remaining]
            if not content:
                continue
            evidence.append(
                RetrievedCandidate(
                    document=candidate.document.model_copy(
                        update={"page_content": content}
                    ),
                    hybrid_score=candidate.hybrid_score,
                    rerank_score=candidate.rerank_score,
                )
            )
            remaining -= len(content)
        return evidence

    def answer(
        self,
        question: str,
        candidates: Sequence[RetrievedCandidate],
        *,
        request_id: str | None = None,
        question_triage: QuestionTriage,
        on_stage: FlowCallback | None = None,
    ) -> QueryResponse:
        request_id = request_id or str(uuid.uuid4())
        if question_triage.sensitive_data_types:
            self._skip_answer_stages(
                request_id,
                on_stage,
                "Sensitive data was detected during triage",
            )
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

        gate_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="evidence_gate",
            status=FlowStatus.RUNNING,
            message="Checking whether retrieved evidence is strong enough to answer",
            data={"context_count": len(candidates)},
        )
        confidence = self.confidence_grader.grade(candidates)
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="evidence_gate",
            status=FlowStatus.COMPLETED,
            message=f"Evidence confidence classified as {confidence.value}",
            duration_ms=(time.perf_counter() - gate_started) * 1_000,
            data={"confidence": confidence.value},
        )
        if not candidates:
            self._skip_generation(request_id, on_stage, "No retrievable evidence was found")
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
            self._skip_generation(
                request_id,
                on_stage,
                "Evidence confidence did not meet the answer threshold",
            )
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

        evidence = self.prepare_evidence(candidates)
        if not evidence:
            self._skip_generation(
                request_id,
                on_stage,
                "No evidence fit within the configured answer context budget",
            )
            return QueryResponse(
                request_id=request_id,
                category=question_triage.category,
                confidence=ConfidenceLevel.LOW,
                requires_human_review=True,
                routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                answered=False,
                answer=(
                    "The indexed documentation does not contain usable textual evidence. "
                    "Human review is required; route this ticket to customer support."
                ),
                escalation_reasons=[HumanReviewReason.INSUFFICIENT_CONTEXT],
            )

        source_payload: list[dict[str, str]] = []
        citations: list[Citation] = []
        for candidate in evidence:
            metadata = candidate.document.metadata
            content = candidate.document.page_content
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
                    document_checksum=(
                        str(metadata["checksum"]) if metadata.get("checksum") else None
                    ),
                    chunk_id=(
                        str(metadata["chunk_id"]) if metadata.get("chunk_id") else None
                    ),
                )
            )

        invoke_payload = {
            "question": question,
            "sources": json.dumps(source_payload, ensure_ascii=False),
        }
        generation_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="generate",
            status=FlowStatus.RUNNING,
            message="Generating an answer from the selected evidence only",
            data={"source_count": len(source_payload)},
        )
        last_error: Exception | None = None
        for _ in range(self.settings.model_retry_attempts):
            try:
                raw_answer = self._chain.invoke(invoke_payload).strip()
                break
            except Exception as exc:
                last_error = exc
        else:
            emit_flow_event(
                on_stage,
                operation_id=request_id,
                stage="generate",
                status=FlowStatus.FAILED,
                message="Answer generation failed after configured retries",
                duration_ms=(time.perf_counter() - generation_started) * 1_000,
            )
            raise RuntimeError("Answer generation failed after retries") from last_error
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="generate",
            status=FlowStatus.COMPLETED,
            message="Grounded answer draft generated",
            duration_ms=(time.perf_counter() - generation_started) * 1_000,
            data={"answer_characters": len(raw_answer)},
        )
        if raw_answer == "NOT_FOUND" or not raw_answer:
            emit_flow_event(
                on_stage,
                operation_id=request_id,
                stage="citations",
                status=FlowStatus.SKIPPED,
                message="The model abstained before citation validation",
            )
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
        citation_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="citations",
            status=FlowStatus.RUNNING,
            message="Validating cited source IDs against the supplied evidence",
        )
        cited_source_ids = set(re.findall(r"\[(S\d+)\]", raw_answer))
        used_citations = [
            citation for citation in citations if citation.source_id in cited_source_ids
        ]
        if not used_citations:
            emit_flow_event(
                on_stage,
                operation_id=request_id,
                stage="citations",
                status=FlowStatus.COMPLETED,
                message="No valid evidence citation was found; answer rejected",
                duration_ms=(time.perf_counter() - citation_started) * 1_000,
                data={"valid": False},
            )
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
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="citations",
            status=FlowStatus.COMPLETED,
            message="Citations validated against retrieved evidence",
            duration_ms=(time.perf_counter() - citation_started) * 1_000,
            data={"valid": True, "citation_count": len(used_citations)},
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

    @staticmethod
    def _skip_generation(
        request_id: str,
        callback: FlowCallback | None,
        reason: str,
    ) -> None:
        for stage in ("generate", "citations"):
            emit_flow_event(
                callback,
                operation_id=request_id,
                stage=stage,
                status=FlowStatus.SKIPPED,
                message=reason,
            )

    @classmethod
    def _skip_answer_stages(
        cls,
        request_id: str,
        callback: FlowCallback | None,
        reason: str,
    ) -> None:
        emit_flow_event(
            callback,
            operation_id=request_id,
            stage="evidence_gate",
            status=FlowStatus.SKIPPED,
            message=reason,
        )
        cls._skip_generation(request_id, callback, reason)
