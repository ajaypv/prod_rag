from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from prodrag.answering import GroundedAnswerService
from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import (
    ConfidenceLevel,
    HumanReviewReason,
    RoutingDestination,
    TicketCategory,
)
from prodrag.retrieval.confidence import ScoreThresholdConfidenceGrader
from prodrag.triage import QuestionTriage


def _decision(
    *,
    category: TicketCategory = TicketCategory.OTHER,
    policy_review: bool = False,
) -> QuestionTriage:
    return QuestionTriage(
        category=category,
        sensitive_data_types=(),
        policy_review_required=policy_review,
        classification_confidence=ConfidenceLevel.HIGH,
    )


def _answer_service(*responses: str) -> GroundedAnswerService:
    settings = Settings(_env_file=None)
    return GroundedAnswerService(
        settings,
        FakeListChatModel(responses=list(responses)),
        ScoreThresholdConfidenceGrader(settings),
    )


def test_answer_service_abstains_without_context() -> None:
    service = _answer_service()

    response = service.answer("Unknown?", [], question_triage=_decision())

    assert response.answered is False
    assert response.confidence == ConfidenceLevel.LOW
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.escalation_reasons == [HumanReviewReason.INSUFFICIENT_CONTEXT]
    assert response.citations == []
    assert "Human review is required" in response.answer


def test_answer_service_returns_source_metadata() -> None:
    service = _answer_service("Use the reset command. [S1]")
    candidate = RetrievedCandidate(
        Document(
            page_content="Run reset-service.",
            metadata={
                "document_id": "runbook",
                "title": "Runbook",
                "section": "Recovery",
                "source_name": "runbook.md",
            },
        ),
        hybrid_score=0.9,
        rerank_score=0.95,
    )

    response = service.answer(
        "How do I reset it?",
        [candidate],
        request_id="request-1",
        question_triage=_decision(),
    )

    assert response.answered is True
    assert response.category == TicketCategory.OTHER
    assert response.confidence == ConfidenceLevel.HIGH
    assert response.requires_human_review is False
    assert response.routing_destination is None
    assert response.request_id == "request-1"
    assert response.citations[0].source_id == "S1"
    assert response.citations[0].document_id == "runbook"


def test_answer_service_normalizes_full_width_source_citations() -> None:
    service = _answer_service("Wait for Retry-After before retrying.\u3010S1\u3011")
    candidate = RetrievedCandidate(
        Document(
            page_content="Wait for Retry-After before retrying.",
            metadata={"document_id": "rate-limits"},
        ),
        hybrid_score=0.9,
        rerank_score=0.95,
    )

    response = service.answer(
        "What should I do after HTTP 429?",
        [candidate],
        question_triage=_decision(category=TicketCategory.API_LIMITS),
    )

    assert response.answered is True
    assert response.answer.endswith("[S1]")
    assert response.citations[0].source_id == "S1"


def test_answer_service_normalizes_spaced_source_citations() -> None:
    service = _answer_service("Open Settings > Billing > Invoices. [ S1 ]")
    candidate = RetrievedCandidate(
        Document(
            page_content="Invoices are under Settings > Billing > Invoices.",
            metadata={"document_id": "faq", "source_name": "faq.html"},
        ),
        hybrid_score=0.9,
        rerank_score=0.95,
    )

    response = service.answer(
        "Where can I download an invoice?",
        [candidate],
        question_triage=_decision(category=TicketCategory.BILLING),
    )

    assert response.answered is True
    assert response.answer.endswith("[S1]")
    assert response.citations[0].source_name == "faq.html"

def test_answer_service_rejects_an_uncited_answer() -> None:
    service = _answer_service("Use the reset command.")
    candidate = RetrievedCandidate(
        Document(page_content="Run reset-service.", metadata={"document_id": "runbook"}),
        hybrid_score=0.9,
    )

    response = service.answer(
        "How do I reset it?",
        [candidate],
        question_triage=_decision(),
    )

    assert response.answered is False
    assert response.confidence == ConfidenceLevel.LOW
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.escalation_reasons == [HumanReviewReason.MISSING_CITATIONS]
    assert response.citations == []


def test_answer_service_escalates_low_retrieval_confidence_without_model_call() -> None:
    service = _answer_service()
    candidate = RetrievedCandidate(
        Document(page_content="Maybe relevant.", metadata={"document_id": "weak"}),
        hybrid_score=0.2,
        rerank_score=0.2,
    )

    response = service.answer(
        "Why was I charged?",
        [candidate],
        question_triage=_decision(category=TicketCategory.BILLING),
    )

    assert response.category == TicketCategory.BILLING
    assert response.confidence == ConfidenceLevel.LOW
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.escalation_reasons == [HumanReviewReason.LOW_CONFIDENCE]


def test_grounded_policy_answer_still_requires_human_review() -> None:
    service = _answer_service("Billing Operations must review the refund. [S1]")
    candidate = RetrievedCandidate(
        Document(page_content="Refund requests need review.", metadata={"document_id": "billing"}),
        hybrid_score=0.9,
        rerank_score=0.95,
    )

    response = service.answer(
        "Please refund a duplicate charge of USD 900",
        [candidate],
        question_triage=_decision(
            category=TicketCategory.BILLING,
            policy_review=True,
        ),
    )

    assert response.answered is True
    assert response.confidence == ConfidenceLevel.HIGH
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.escalation_reasons == [HumanReviewReason.POLICY_RULE]
