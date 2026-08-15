from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from prodrag.api import app
from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import (
    ConfidenceLevel,
    EvaluationJobStatus,
    FlowEvent,
    FlowStatus,
    JobState,
    JobStatus,
    QueryResponse,
    TicketCategory,
)
from prodrag.querying import QueryExecution
from prodrag.security import AuthContext, require_admin_key, require_query_key


class FakeJobStore:
    def get(self, job_id: str) -> JobStatus:
        return JobStatus(
            job_id=job_id,
            state=JobState.SUCCEEDED,
            document_id="guide",
            tenant_id="other",
        )


def test_query_rejects_cross_tenant_request() -> None:
    app.dependency_overrides[require_query_key] = lambda: AuthContext(tenant_id="acme")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/query",
                json={"question": "How do I reset it?", "tenant_id": "other"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_job_status_rejects_cross_tenant_lookup(monkeypatch) -> None:
    app.dependency_overrides[require_admin_key] = lambda: AuthContext(tenant_id="acme")
    monkeypatch.setattr("prodrag.api.get_job_store", lambda: FakeJobStore())
    try:
        with TestClient(app) as client:
            response = client.get("/v1/ingestions/job-1")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


class FakeStreamingQueryService:
    def query_with_evidence(self, request, *, request_id: str, on_stage):
        on_stage(
            FlowEvent(
                operation_id=request_id,
                stage="triage",
                status=FlowStatus.COMPLETED,
                message="Query classification completed",
            )
        )
        return QueryExecution(
            response=QueryResponse(
                request_id=request_id,
                category=TicketCategory.OTHER,
                confidence=ConfidenceLevel.HIGH,
                requires_human_review=False,
                answered=True,
                answer="Grounded answer [S1]",
            ),
            contexts=(
                RetrievedCandidate(
                    Document(
                        page_content="Supporting evidence",
                        metadata={
                            "document_id": "guide",
                            "title": "Guide",
                            "section": "Retention",
                            "source_name": "guide.md",
                        },
                    ),
                    hybrid_score=0.9,
                ),
            ),
        )


def test_query_stream_returns_stage_event_result_and_evidence(monkeypatch) -> None:
    app.dependency_overrides[require_query_key] = lambda: AuthContext(tenant_id="default")
    monkeypatch.setattr(
        "prodrag.api.get_query_service",
        lambda: FakeStreamingQueryService(),
    )
    try:
        with TestClient(app) as client, client.stream(
            "POST",
            "/v1/query/stream",
            json={"question": "How long?", "tenant_id": "default"},
        ) as response:
            body = "".join(response.iter_text())
        assert response.status_code == 200
        assert '"type": "stage"' in body
        assert '"stage": "triage"' in body
        assert '"type": "result"' in body
        assert '"excerpt": "Supporting evidence"' in body
    finally:
        app.dependency_overrides.clear()


class FakeEvaluationJobStore:
    def __init__(self) -> None:
        self.status: EvaluationJobStatus | None = None

    def put_evaluation(self, status: EvaluationJobStatus) -> None:
        self.status = status


class FakeEvaluationActor:
    def __init__(self) -> None:
        self.arguments: tuple | None = None

    def send(self, *arguments) -> None:
        self.arguments = arguments


def test_evaluation_upload_is_queued_with_real_stage_history(
    monkeypatch,
    tmp_path: Path,
) -> None:
    job_store = FakeEvaluationJobStore()
    actor = FakeEvaluationActor()
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        qdrant_hnsw_enabled=False,
    )
    app.dependency_overrides[require_admin_key] = lambda: AuthContext(tenant_id="default")
    monkeypatch.setattr("prodrag.api.get_job_store", lambda: job_store)
    monkeypatch.setattr("prodrag.api.get_settings", lambda: settings)
    monkeypatch.setattr("prodrag.api.evaluate_dataset", actor)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/evaluations",
                data={"tenant_id": "default", "end_to_end": "false"},
                files={"file": ("golden.jsonl", b'{"question":"one"}\n', "application/jsonl")},
            )
        assert response.status_code == 202
        assert job_store.status is not None
        assert job_store.status.events[0].stage == "queued"
        assert actor.arguments is not None
        assert actor.arguments[2:] == ("default", False, False)
    finally:
        app.dependency_overrides.clear()
