from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from prodrag.config import SUPPORTED_EXTENSIONS, get_settings
from prodrag.container import (
    get_index,
    get_job_store,
    get_query_service,
)
from prodrag.models import (
    HealthResponse,
    IngestionAccepted,
    JobState,
    JobStatus,
    QueryRequest,
    QueryResponse,
)
from prodrag.security import require_admin_key, require_query_key
from prodrag.worker import ingest_document

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    (settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="prodRAG",
    version="0.1.0",
    description="OCI GenAI RAG with local Qdrant hybrid retrieval",
    lifespan=lifespan,
)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    checks: dict[str, str] = {}
    for name, check in (
        ("qdrant", get_index().ping),
        ("redis", get_job_store().ping),
    ):
        try:
            await run_in_threadpool(check)
            checks[name] = "ok"
        except Exception as exc:
            checks[name] = f"failed: {type(exc).__name__}"
    if any(result != "ok" for result in checks.values()):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=checks)
    return HealthResponse(status="ready", checks=checks)


@app.post(
    "/v1/documents",
    response_model=IngestionAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin_key)],
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    document_id: Annotated[str | None, Form()] = None,
    tenant_id: Annotated[str, Form(min_length=1, max_length=100)] = "default",
    product: Annotated[str | None, Form(max_length=100)] = None,
    version: Annotated[str | None, Form(max_length=100)] = None,
) -> IngestionAccepted:
    settings = get_settings()
    original_name = Path(file.filename or "upload").name
    extension = Path(original_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Supported file types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    document_id = document_id or str(uuid.uuid4())
    if not _SAFE_ID_RE.fullmatch(document_id):
        raise HTTPException(status_code=422, detail="document_id contains unsupported characters")
    if not _SAFE_ID_RE.fullmatch(tenant_id):
        raise HTTPException(status_code=422, detail="tenant_id contains unsupported characters")

    job_id = str(uuid.uuid4())
    safe_name = _SAFE_FILENAME_RE.sub("_", original_name).strip("._") or f"document{extension}"
    upload_dir = settings.data_dir / "uploads" / document_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{job_id}-{safe_name}"

    size = 0
    try:
        with target.open("xb") as output:
            while block := await file.read(1024 * 1024):
                size += len(block)
                if size > settings.max_file_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.max_file_mb} MB limit",
                    )
                output.write(block)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded document is empty")

    queued = JobStatus(
        job_id=job_id,
        state=JobState.QUEUED,
        document_id=document_id,
        updated_at=datetime.now(UTC),
    )
    job_store = get_job_store()
    try:
        await run_in_threadpool(job_store.put, queued)
        ingest_document.send(
            job_id,
            str(target.resolve()),
            document_id,
            tenant_id,
            product or None,
            version or None,
        )
    except Exception as exc:
        failed = queued.model_copy(
            update={
                "state": JobState.FAILED,
                "message": f"Queue unavailable: {type(exc).__name__}",
                "updated_at": datetime.now(UTC),
            }
        )
        with suppress(Exception):
            await run_in_threadpool(job_store.put, failed)
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Ingestion queue is unavailable") from exc
    return IngestionAccepted(job_id=job_id, document_id=document_id)


@app.get(
    "/v1/ingestions/{job_id}",
    response_model=JobStatus,
    dependencies=[Depends(require_admin_key)],
)
async def ingestion_status(job_id: str) -> JobStatus:
    result = await run_in_threadpool(get_job_store().get, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found or expired")
    return result


@app.delete(
    "/v1/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_key)],
)
async def delete_document(document_id: str, tenant_id: str = "default") -> None:
    if not _SAFE_ID_RE.fullmatch(document_id):
        raise HTTPException(status_code=422, detail="Invalid document_id")
    if not _SAFE_ID_RE.fullmatch(tenant_id):
        raise HTTPException(status_code=422, detail="Invalid tenant_id")
    await run_in_threadpool(get_index().delete_document, document_id, tenant_id=tenant_id)


@app.post(
    "/v1/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_query_key)],
)
async def query(request: QueryRequest) -> QueryResponse:
    return await run_in_threadpool(get_query_service().query, request)
