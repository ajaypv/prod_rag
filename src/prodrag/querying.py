from __future__ import annotations

import uuid
from dataclasses import dataclass

from prodrag.answering import GroundedAnswerService
from prodrag.domain import RetrievedCandidate
from prodrag.models import (
    ConfidenceLevel,
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
        self, request: QueryRequest, *, request_id: str | None = None
    ) -> QueryExecution:
        """Run a query while retaining retrieved contexts for offline quality evaluation."""
        request_id = request_id or str(uuid.uuid4())
        try:
            preflight = self.triage.inspect_question(request.question)
        except TriageClassificationError:
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
        if preflight.sensitive_data_types:
            return QueryExecution(
                response=self.answer_service.answer(
                    request.question,
                    [],
                    request_id=request_id,
                    question_triage=preflight,
                ),
                contexts=(),
            )
        if preflight.classification_confidence == ConfidenceLevel.LOW:
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
        )
        return QueryExecution(
            response=self.answer_service.answer(
                request.question,
                contexts,
                request_id=request_id,
                question_triage=preflight,
            ),
            # Keep precisely the same truncated evidence used to build S1, S2, ... in the
            # answer prompt; offline faithfulness must not inspect unseen parent text.
            contexts=tuple(self.answer_service.prepare_evidence(contexts)),
        )
