from fastapi.testclient import TestClient

from prodrag.api import app
from prodrag.models import JobState, JobStatus
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
