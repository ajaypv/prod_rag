from __future__ import annotations

import asyncio
import json
import re
import subprocess
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from prodrag.config import SUPPORTED_EXTENSIONS, get_settings
from prodrag.container import (
    get_index,
    get_job_store,
    get_query_service,
)
from prodrag.models import (
    EvaluationAccepted,
    EvaluationJobStatus,
    EvaluationStage,
    FlowEvent,
    FlowStatus,
    HealthResponse,
    IngestionAccepted,
    JobState,
    JobStatus,
    QueryRequest,
    QueryResponse,
)
from prodrag.observability import (
    configure_logging,
    metrics,
    request_observability_middleware,
)
from prodrag.security import (
    AuthContext,
    authorize_tenant,
    require_admin_key,
    require_query_key,
)
from prodrag.worker import evaluate_dataset, ingest_document

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _scan_upload(target: Path) -> None:
    settings = get_settings()
    if not settings.upload_scan_command:
        return
    command = [part.replace("{path}", str(target)) for part in settings.upload_scan_command]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=settings.upload_scan_timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=503, detail="Upload scanner is unavailable") from exc
    if result.returncode != 0:
        raise HTTPException(status_code=422, detail="The uploaded document failed security scan")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    (settings.data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="prodRAG",
    version="0.1.0",
    description="OCI GenAI RAG with local Qdrant hybrid retrieval",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Key", "X-API-Key"],
)
app.middleware("http")(request_observability_middleware)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def prometheus_metrics() -> PlainTextResponse:
    if not get_settings().metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics are disabled")
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")


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
)
async def upload_document(
    auth: Annotated[AuthContext, Depends(require_admin_key)],
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
    authorize_tenant(auth, tenant_id)

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
    try:
        await run_in_threadpool(_scan_upload, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    queued = JobStatus(
        job_id=job_id,
        state=JobState.QUEUED,
        document_id=document_id,
        tenant_id=tenant_id,
        stage="queued",
        message="Upload accepted and queued for ingestion",
        events=[
            FlowEvent(
                operation_id=job_id,
                stage="upload",
                status=FlowStatus.COMPLETED,
                message="Document upload and security checks completed",
                data={"filename": original_name, "bytes": size},
            ),
            FlowEvent(
                operation_id=job_id,
                stage="queued",
                status=FlowStatus.COMPLETED,
                message="Ingestion job added to the worker queue",
            ),
        ],
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
)
async def ingestion_status(
    job_id: str, auth: Annotated[AuthContext, Depends(require_admin_key)]
) -> JobStatus:
    result = await run_in_threadpool(get_job_store().get, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found or expired")
    authorize_tenant(auth, result.tenant_id)
    return result


@app.delete(
    "/v1/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: str,
    auth: Annotated[AuthContext, Depends(require_admin_key)],
    tenant_id: str = "default",
) -> None:
    if not _SAFE_ID_RE.fullmatch(document_id):
        raise HTTPException(status_code=422, detail="Invalid document_id")
    if not _SAFE_ID_RE.fullmatch(tenant_id):
        raise HTTPException(status_code=422, detail="Invalid tenant_id")
    authorize_tenant(auth, tenant_id)
    await run_in_threadpool(get_index().delete_document, document_id, tenant_id=tenant_id)


@app.post(
    "/v1/query",
    response_model=QueryResponse,
)
async def query(
    request: QueryRequest,
    auth: Annotated[AuthContext, Depends(require_query_key)],
) -> QueryResponse:
    authorize_tenant(auth, request.tenant_id)
    try:
        async with asyncio.timeout(get_settings().query_timeout_seconds):
            return await run_in_threadpool(get_query_service().query, request)
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Query processing timed out") from exc


@app.post("/v1/query/stream")
async def query_stream(
    request: QueryRequest,
    auth: Annotated[AuthContext, Depends(require_query_key)],
) -> StreamingResponse:
    """Stream genuine query-stage events followed by the normal response and evidence."""
    authorize_tenant(auth, request.tenant_id)
    request_id = str(uuid.uuid4())
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def record(event: FlowEvent) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "stage", "event": event.model_dump(mode="json")},
        )

    async def execute() -> None:
        try:
            async with asyncio.timeout(get_settings().query_timeout_seconds):
                execution = await run_in_threadpool(
                    partial(
                        get_query_service().query_with_evidence,
                        request,
                        request_id=request_id,
                        on_stage=record,
                    )
                )
            evidence = []
            for item in execution.contexts:
                metadata = item.document.metadata
                evidence.append(
                    {
                        "document_id": str(metadata.get("document_id", "")),
                        "title": str(metadata.get("title", "Untitled")),
                        "section": str(metadata.get("section", "Document")),
                        "source_name": str(metadata.get("source_name", "unknown")),
                        "score": round(item.final_score, 6),
                        "excerpt": item.document.page_content[:600],
                    }
                )
            await queue.put(
                {
                    "type": "result",
                    "response": execution.response.model_dump(mode="json"),
                    "evidence": evidence,
                }
            )
        except TimeoutError:
            await queue.put(
                {
                    "type": "error",
                    "status": 504,
                    "detail": "Query processing timed out",
                }
            )
        except Exception as exc:
            await queue.put(
                {
                    "type": "error",
                    "status": 500,
                    "detail": f"Query flow failed: {type(exc).__name__}",
                }
            )

    task = asyncio.create_task(execute())

    async def stream():
        try:
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if payload["type"] in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post(
    "/v1/evaluations",
    response_model=EvaluationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_evaluation(
    auth: Annotated[AuthContext, Depends(require_admin_key)],
    file: Annotated[UploadFile, File()],
    tenant_id: Annotated[str, Form(min_length=1, max_length=100)] = "default",
    end_to_end: Annotated[bool, Form()] = True,
    deep_eval: Annotated[bool, Form()] = False,
) -> EvaluationAccepted:
    if Path(file.filename or "").suffix.lower() != ".jsonl":
        raise HTTPException(status_code=415, detail="Evaluation datasets must be JSONL files")
    if deep_eval and not end_to_end:
        raise HTTPException(status_code=422, detail="DeepEval requires end-to-end evaluation")
    if not _SAFE_ID_RE.fullmatch(tenant_id):
        raise HTTPException(status_code=422, detail="tenant_id contains unsupported characters")
    authorize_tenant(auth, tenant_id)

    settings = get_settings()
    job_id = str(uuid.uuid4())
    evaluation_dir = settings.data_dir / "evaluations"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    target = evaluation_dir / f"{job_id}-dataset.jsonl"
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
        raise HTTPException(status_code=422, detail="Evaluation dataset is empty")
    try:
        await run_in_threadpool(_scan_upload, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    queued = EvaluationJobStatus(
        job_id=job_id,
        state=JobState.QUEUED,
        tenant_id=tenant_id,
        stage=EvaluationStage.QUEUED,
        deep_eval=deep_eval,
        message="Evaluation queued",
        events=[
            FlowEvent(
                operation_id=job_id,
                stage=EvaluationStage.QUEUED.value,
                status=FlowStatus.COMPLETED,
                message="Golden dataset uploaded and queued",
                data={"bytes": size},
            )
        ],
    )
    job_store = get_job_store()
    try:
        await run_in_threadpool(job_store.put_evaluation, queued)
        evaluate_dataset.send(
            job_id,
            str(target.resolve()),
            tenant_id,
            end_to_end,
            deep_eval,
        )
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Evaluation queue is unavailable") from exc
    return EvaluationAccepted(job_id=job_id)


@app.get("/v1/evaluations/{job_id}", response_model=EvaluationJobStatus)
async def evaluation_status(
    job_id: str,
    auth: Annotated[AuthContext, Depends(require_admin_key)],
) -> EvaluationJobStatus:
    result = await run_in_threadpool(get_job_store().get_evaluation, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found or expired")
    authorize_tenant(auth, result.tenant_id)
    return result
