from __future__ import annotations

import uuid

from prodrag.answering import GroundedAnswerService
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
        request_id = request_id or str(uuid.uuid4())
        try:
            preflight = self.triage.inspect_question(request.question)
        except TriageClassificationError:
            return QueryResponse(
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
            )
        if preflight.sensitive_data_types:
            return self.answer_service.answer(
                request.question,
                [],
                request_id=request_id,
                question_triage=preflight,
            )
        if preflight.classification_confidence == ConfidenceLevel.LOW:
            return QueryResponse(
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
            )

        contexts = self.retrieval.retrieve(
            request.question,
            tenant_id=request.tenant_id,
            product=request.product,
            version=request.version,
        )
        return self.answer_service.answer(
            request.question,
            contexts,
            request_id=request_id,
            question_triage=preflight,
        )
