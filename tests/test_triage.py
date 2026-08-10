import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from prodrag.answering import GroundedAnswerService
from prodrag.config import Settings
from prodrag.models import (
    ConfidenceLevel,
    HumanReviewReason,
    QueryRequest,
    RoutingDestination,
    SensitiveDataType,
    TicketCategory,
)
from prodrag.querying import QueryService
from prodrag.retrieval.confidence import ScoreThresholdConfidenceGrader
from prodrag.triage import TicketTriageService


class RetrievalMustNotRun:
    def retrieve(self, *args, **kwargs):
        raise AssertionError("retrieval must not run for escalated questions")


def _triage_response(
    *,
    category: TicketCategory = TicketCategory.OTHER,
    sensitive: list[SensitiveDataType] | None = None,
    policy_review: bool = False,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> str:
    return json.dumps(
        {
            "category": category,
            "sensitive_data_types": sensitive or [],
            "policy_review_required": policy_review,
            "classification_confidence": confidence,
        }
    )


def _triage_service(*responses: str) -> TicketTriageService:
    return TicketTriageService(FakeListChatModel(responses=list(responses)))


def test_llm_ticket_categories_cover_demo_use_cases() -> None:
    expected = [
        TicketCategory.BILLING,
        TicketCategory.API_LIMITS,
        TicketCategory.INTEGRATION_ERROR,
        TicketCategory.ACCOUNT_SECURITY,
        TicketCategory.OTHER,
    ]
    triage = _triage_service(
        *[_triage_response(category=category) for category in expected]
    )
    questions = [
        "Why is my invoice past due?",
        "Why do I receive HTTP 429?",
        "My webhook signature fails",
        "How do I rotate an API key?",
        "Where is the dark mode setting?",
    ]

    assert [triage.inspect_question(question).category for question in questions] == expected


def test_llm_sensitive_data_classifier_returns_types_without_values() -> None:
    triage = _triage_service(
        _triage_response(
            category=TicketCategory.ACCOUNT_SECURITY,
            sensitive=[
                SensitiveDataType.PAYMENT_CARD,
                SensitiveDataType.CREDENTIAL,
            ],
        )
    )

    result = triage.inspect_question(
        "The customer supplied an API secret and a payment-card value"
    )

    assert result.sensitive_data_types == (
        SensitiveDataType.CREDENTIAL,
        SensitiveDataType.PAYMENT_CARD,
    )


def test_llm_policy_decision_is_preserved() -> None:
    triage = _triage_service(
        _triage_response(category=TicketCategory.BILLING, policy_review=True),
        _triage_response(category=TicketCategory.API_LIMITS, policy_review=True),
        _triage_response(category=TicketCategory.API_LIMITS),
    )

    refund = triage.inspect_question("Please refund a duplicate charge of USD 900")
    capacity = triage.inspect_question("We need a permanent API limit increase")
    routine = triage.inspect_question("What is the Growth API limit?")

    assert refund.policy_review_required is True
    assert capacity.policy_review_required is True
    assert routine.policy_review_required is False


def test_sensitive_question_is_escalated_before_retrieval() -> None:
    settings = Settings(_env_file=None)
    triage = _triage_service(
        _triage_response(
            category=TicketCategory.ACCOUNT_SECURITY,
            sensitive=[SensitiveDataType.GOVERNMENT_ID],
        )
    )
    answer_service = GroundedAnswerService(
        settings,
        FakeListChatModel(responses=[]),
        ScoreThresholdConfidenceGrader(settings),
    )
    service = QueryService(
        RetrievalMustNotRun(),  # type: ignore[arg-type]
        answer_service,
        triage,
    )

    response = service.query(QueryRequest(question="My SSN is 123-45-6789"))

    assert response.answered is False
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.confidence == ConfidenceLevel.LOW
    assert response.escalation_reasons == [HumanReviewReason.SENSITIVE_DATA]
    assert response.sensitive_data_types == [SensitiveDataType.GOVERNMENT_ID]


def test_invalid_llm_triage_fails_closed_to_customer_support() -> None:
    settings = Settings(_env_file=None)
    triage = _triage_service("This is not JSON")
    answer_service = GroundedAnswerService(
        settings,
        FakeListChatModel(responses=[]),
        ScoreThresholdConfidenceGrader(settings),
    )
    service = QueryService(
        RetrievalMustNotRun(),  # type: ignore[arg-type]
        answer_service,
        triage,
    )

    response = service.query(QueryRequest(question="Please inspect my account"))

    assert response.answered is False
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.escalation_reasons == [HumanReviewReason.TRIAGE_FAILURE]


def test_low_confidence_llm_triage_routes_to_customer_support() -> None:
    settings = Settings(_env_file=None)
    triage = _triage_service(_triage_response(confidence=ConfidenceLevel.LOW))
    answer_service = GroundedAnswerService(
        settings,
        FakeListChatModel(responses=[]),
        ScoreThresholdConfidenceGrader(settings),
    )
    service = QueryService(
        RetrievalMustNotRun(),  # type: ignore[arg-type]
        answer_service,
        triage,
    )

    response = service.query(QueryRequest(question="Please inspect my account"))

    assert response.answered is False
    assert response.requires_human_review is True
    assert response.routing_destination == RoutingDestination.CUSTOMER_SUPPORT
    assert response.escalation_reasons == [HumanReviewReason.TRIAGE_UNCERTAIN]
