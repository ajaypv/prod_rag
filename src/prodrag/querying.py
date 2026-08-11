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
    """Orchestrate the command behind ``prodrag query`` from safety to answer.

    Normal flow::

        question -> OCI triage -> hybrid retrieval -> OCI rerank -> confidence gate
                 -> OCI grounded answer -> citation validation -> JSON response

    Sensitive, uncertain, or malformed triage results stop before the query is embedded. This
    is both a privacy boundary and a fail-closed safety decision.
    """

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
        """Run one query and preserve a request ID across every possible exit path.

        ``product`` and ``version`` are retrieval filters, not words appended to the question.
        This prevents a result from another product/version from entering the candidate pool.
        """
        request_id = request_id or str(uuid.uuid4())
        try:
            preflight = self.triage.inspect_question(request.question)
        except TriageClassificationError:
            # Fail closed when the structured safety classification cannot be trusted.
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
            # Do not embed or retrieve with a question that contains detected sensitive data.
            return self.answer_service.answer(
                request.question,
                [],
                request_id=request_id,
                question_triage=preflight,
            )
        if preflight.classification_confidence == ConfidenceLevel.LOW:
            # Uncertain classification is routed to a person before any retrieval/model answer.
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
