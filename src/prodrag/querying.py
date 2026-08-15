from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from prodrag.answering import GroundedAnswerService
from prodrag.domain import RetrievedCandidate
from prodrag.flow import FlowCallback, emit_flow_event
from prodrag.models import (
    ConfidenceLevel,
    FlowStatus,
    HumanReviewReason,
    QueryRequest,
    QueryResponse,
    RoutingDestination,
    TicketCategory,
)
from prodrag.retrieval import RetrievalService
from prodrag.triage import TicketTriageService, TriageClassificationError


@dataclass(frozen=True, slots=True)
class QueryExecution:
    """Internal evaluation trace containing the public response and evidence it used."""

    response: QueryResponse
    contexts: tuple[RetrievedCandidate, ...]


class QueryService:
    """Run local preflight checks before retrieval and answer generation."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        answer_service: GroundedAnswerService,
        triage_service: TicketTriageService,
    ) -> None:
        self.retrieval = retrieval_service
        self.answer_service = answer_service
        self.triage = triage_service

    def query(
        self, request: QueryRequest, *, request_id: str | None = None
    ) -> QueryResponse:
        return self.query_with_evidence(request, request_id=request_id).response

    def query_with_evidence(
        self,
        request: QueryRequest,
        *,
        request_id: str | None = None,
        on_stage: FlowCallback | None = None,
    ) -> QueryExecution:
        """Run a query while retaining retrieved contexts for offline quality evaluation."""
        request_id = request_id or str(uuid.uuid4())
        triage_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="triage",
            status=FlowStatus.RUNNING,
            message="Classifying intent, safety, and routing requirements",
        )
        try:
            preflight = self.triage.inspect_question(request.question)
        except TriageClassificationError:
            emit_flow_event(
                on_stage,
                operation_id=request_id,
                stage="triage",
                status=FlowStatus.FAILED,
                message="Triage model did not return a reliable classification",
                duration_ms=(time.perf_counter() - triage_started) * 1_000,
            )
            self._skip_after_triage(
                request_id,
                on_stage,
                "Query stopped because triage failed closed",
            )
            return QueryExecution(
                response=QueryResponse(
                    request_id=request_id,
                    category=TicketCategory.OTHER,
                    confidence=ConfidenceLevel.LOW,
                    requires_human_review=True,
                    routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                    answered=False,
                    answer=(
                        "The automated safety classification could not be completed reliably. "
                        "Human review is required; route this ticket to customer support."
                    ),
                    escalation_reasons=[HumanReviewReason.TRIAGE_FAILURE],
                ),
                contexts=(),
            )
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="triage",
            status=FlowStatus.COMPLETED,
            message="Query classification completed",
            duration_ms=(time.perf_counter() - triage_started) * 1_000,
            data={
                "category": preflight.category.value,
                "confidence": preflight.classification_confidence.value,
                "sensitive": bool(preflight.sensitive_data_types),
            },
        )
        if preflight.sensitive_data_types:
            self._skip_retrieval(
                request_id,
                on_stage,
                "Sensitive data requires secure human review",
            )
            return QueryExecution(
                response=self.answer_service.answer(
                    request.question,
                    [],
                    request_id=request_id,
                    question_triage=preflight,
                    on_stage=on_stage,
                ),
                contexts=(),
            )
        if preflight.classification_confidence == ConfidenceLevel.LOW:
            self._skip_after_triage(
                request_id,
                on_stage,
                "Low-confidence triage routed the query to human review",
            )
            return QueryExecution(
                response=QueryResponse(
                    request_id=request_id,
                    category=preflight.category,
                    confidence=ConfidenceLevel.LOW,
                    requires_human_review=True,
                    routing_destination=RoutingDestination.CUSTOMER_SUPPORT,
                    answered=False,
                    answer=(
                        "The automated ticket classification is uncertain. Human review is "
                        "required; route this ticket to customer support."
                    ),
                    escalation_reasons=[HumanReviewReason.TRIAGE_UNCERTAIN],
                ),
                contexts=(),
            )

        contexts = self.retrieval.retrieve(
            request.question,
            tenant_id=request.tenant_id,
            product=request.product,
            version=request.version,
            request_id=request_id,
            on_stage=on_stage,
        )
        return QueryExecution(
            response=self.answer_service.answer(
                request.question,
                contexts,
                request_id=request_id,
                question_triage=preflight,
                on_stage=on_stage,
            ),
            # Keep precisely the same truncated evidence used to build S1, S2, ... in the
            # answer prompt; offline faithfulness must not inspect unseen parent text.
            contexts=tuple(self.answer_service.prepare_evidence(contexts)),
        )

    @staticmethod
    def _skip_retrieval(
        request_id: str,
        callback: FlowCallback | None,
        reason: str,
    ) -> None:
        for stage in ("hybrid_retrieval", "rerank", "context"):
            emit_flow_event(
                callback,
                operation_id=request_id,
                stage=stage,
                status=FlowStatus.SKIPPED,
                message=reason,
            )

    @classmethod
    def _skip_after_triage(
        cls,
        request_id: str,
        callback: FlowCallback | None,
        reason: str,
    ) -> None:
        cls._skip_retrieval(request_id, callback, reason)
        for stage in ("evidence_gate", "generate", "citations"):
            emit_flow_event(
                callback,
                operation_id=request_id,
                stage=stage,
                status=FlowStatus.SKIPPED,
                message=reason,
            )
