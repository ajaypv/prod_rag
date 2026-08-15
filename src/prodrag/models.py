from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FlowStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class EvaluationStage(StrEnum):
    QUEUED = "queued"
    LOAD_DATASET = "load_dataset"
    RETRIEVAL = "retrieval"
    ANSWER_QUALITY = "answer_quality"
    DEEPEVAL = "deepeval"
    REPORT = "report"


class TicketCategory(StrEnum):
    BILLING = "billing"
    API_LIMITS = "api_limits"
    INTEGRATION_ERROR = "integration_error"
    ACCOUNT_SECURITY = "account_security"
    OTHER = "other"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HumanReviewReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    SENSITIVE_DATA = "sensitive_data"
    POLICY_RULE = "policy_rule"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    MISSING_CITATIONS = "missing_citations"
    TRIAGE_UNCERTAIN = "triage_uncertain"
    TRIAGE_FAILURE = "triage_failure"


class RoutingDestination(StrEnum):
    CUSTOMER_SUPPORT = "customer_support"


class SensitiveDataType(StrEnum):
    CREDENTIAL = "credential"
    PAYMENT_CARD = "payment_card"
    GOVERNMENT_ID = "government_id"
    PRIVATE_KEY = "private_key"
    PERSONAL_DATA = "personal_data"
    FINANCIAL_DATA = "financial_data"
    HEALTH_DATA = "health_data"


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4_000)
    tenant_id: str = Field(default="default", min_length=1, max_length=100)
    product: str | None = Field(default=None, max_length=100)
    version: str | None = Field(default=None, max_length=100)


class Citation(BaseModel):
    source_id: str
    document_id: str
    title: str
    section: str
    source_name: str
    relevance_score: float
    document_checksum: str | None = None
    chunk_id: str | None = None


class QueryResponse(BaseModel):
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


class IngestionAccepted(BaseModel):
    job_id: str
    document_id: str
    state: JobState = JobState.QUEUED


class IngestionResult(BaseModel):
    document_id: str
    checksum: str
    parents_indexed: int
    chunks_indexed: int


class FlowEvent(BaseModel):
    operation_id: str
    stage: str
    status: FlowStatus
    message: str
    duration_ms: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobStatus(BaseModel):
    job_id: str
    state: JobState
    document_id: str
    tenant_id: str = "default"
    stage: str = "queued"
    message: str | None = None
    result: IngestionResult | None = None
    events: list[FlowEvent] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvaluationAccepted(BaseModel):
    job_id: str
    state: JobState = JobState.QUEUED


class EvaluationJobStatus(BaseModel):
    job_id: str
    state: JobState
    tenant_id: str = "default"
    stage: EvaluationStage = EvaluationStage.QUEUED
    deep_eval: bool = False
    message: str | None = None
    metrics: dict[str, Any] | None = None
    events: list[FlowEvent] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, Any] = Field(default_factory=dict)
