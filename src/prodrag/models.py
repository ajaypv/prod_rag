from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TicketCategory(StrEnum):
    """Stable ticket labels printed in CLI query JSON."""
    BILLING = "billing"
    API_LIMITS = "api_limits"
    INTEGRATION_ERROR = "integration_error"
    ACCOUNT_SECURITY = "account_security"
    OTHER = "other"


class ConfidenceLevel(StrEnum):
    """Coarse retrieval confidence derived from the strongest final candidate score."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HumanReviewReason(StrEnum):
    """Machine-readable reasons why the CLI refused or flagged an automatic answer."""
    LOW_CONFIDENCE = "low_confidence"
    SENSITIVE_DATA = "sensitive_data"
    POLICY_RULE = "policy_rule"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    MISSING_CITATIONS = "missing_citations"
    TRIAGE_UNCERTAIN = "triage_uncertain"
    TRIAGE_FAILURE = "triage_failure"


class RoutingDestination(StrEnum):
    """Suggested destination; the CLI reports it but does not create an external ticket."""
    CUSTOMER_SUPPORT = "customer_support"


class SensitiveDataType(StrEnum):
    """Sensitive value categories the triage model may detect in a question."""
    CREDENTIAL = "credential"
    PAYMENT_CARD = "payment_card"
    GOVERNMENT_ID = "government_id"
    PRIVATE_KEY = "private_key"
    PERSONAL_DATA = "personal_data"
    FINANCIAL_DATA = "financial_data"
    HEALTH_DATA = "health_data"


class QueryRequest(BaseModel):
    """Validated input assembled from ``prodrag query`` command-line arguments."""
    question: str = Field(min_length=2, max_length=4_000)
    tenant_id: str = Field(default="default", min_length=1, max_length=100)
    product: str | None = Field(default=None, max_length=100)
    version: str | None = Field(default=None, max_length=100)


class Citation(BaseModel):
    """Source metadata for one parent context actually cited by the generated answer."""
    source_id: str
    document_id: str
    title: str
    section: str
    source_name: str
    relevance_score: float


class QueryResponse(BaseModel):
    """Complete JSON result printed by the query CLI, including safe-abstention details."""
    request_id: str
    category: TicketCategory
    confidence: ConfidenceLevel
    requires_human_review: bool
    routing_destination: RoutingDestination | None = None
    answered: bool
    answer: str
    escalation_reasons: list[HumanReviewReason] = Field(default_factory=list)
    sensitive_data_types: list[SensitiveDataType] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class IngestionResult(BaseModel):
    """Small ingestion summary printed after each file is indexed synchronously."""
    document_id: str
    checksum: str
    parents_indexed: int
    chunks_indexed: int
