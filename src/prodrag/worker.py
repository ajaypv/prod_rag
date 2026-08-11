from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from prodrag.config import get_settings
from prodrag.container import get_ingestion_service, get_job_store
from prodrag.models import JobState, JobStatus
from prodrag.observability import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


def _cleanup_upload(source_path: str) -> None:
    upload_root = (settings.data_dir / "uploads").resolve()
    source = Path(source_path).resolve()
    if not source.is_relative_to(upload_root):
        return
    source.unlink(missing_ok=True)
    with suppress(OSError):
        source.parent.rmdir()


@dramatiq.actor(actor_name="mark_ingestion_failed", queue_name="ingestion")
def mark_ingestion_failed(message_data: dict, retry_metadata: dict) -> None:
    args = message_data.get("args", [])
    if len(args) < 3:
        return
    job_id, _, document_id = args[:3]
    job_store = get_job_store()
    previous = job_store.get(job_id)
    detail = previous.message if previous and previous.message else "Ingestion failed"
    job_store.put(
        JobStatus(
            job_id=job_id,
            state=JobState.FAILED,
            document_id=document_id,
            tenant_id=args[3] if len(args) > 3 else "default",
            message=(
                f"{detail}; retries exhausted after "
                f"{retry_metadata.get('retries', 0)} attempts"
            ),
            updated_at=datetime.now(UTC),
        )
    )
    if len(args) > 1:
        _cleanup_upload(str(args[1]))


@dramatiq.actor(
    queue_name="ingestion",
    max_retries=5,
    min_backoff=5_000,
    max_backoff=300_000,
    time_limit=900_000,
    on_retry_exhausted="mark_ingestion_failed",
)
def ingest_document(
    job_id: str,
    source_path: str,
    document_id: str,
    tenant_id: str,
    product: str | None,
    version: str | None,
) -> None:
    job_store = get_job_store()
    upload_root = (settings.data_dir / "uploads").resolve()
    resolved_source = Path(source_path).resolve(strict=True)
    if not resolved_source.is_relative_to(upload_root):
        raise ValueError("Worker source path is outside the configured upload directory")

    job_store.put(
        JobStatus(
            job_id=job_id,
            state=JobState.RUNNING,
            document_id=document_id,
            tenant_id=tenant_id,
            updated_at=datetime.now(UTC),
        )
    )
    try:
        result = get_ingestion_service().ingest(
            resolved_source,
            document_id=document_id,
            tenant_id=tenant_id,
            product=product,
            version=version,
        )
    except Exception as exc:
        # Dramatiq will retry with exponential backoff; a later attempt overwrites this state.
        job_store.put(
            JobStatus(
                job_id=job_id,
                state=JobState.RETRYING,
                document_id=document_id,
                tenant_id=tenant_id,
                message=f"{type(exc).__name__}: {exc}",
                updated_at=datetime.now(UTC),
            )
        )
        raise
    job_store.put(
        JobStatus(
            job_id=job_id,
            state=JobState.SUCCEEDED,
            document_id=document_id,
            tenant_id=tenant_id,
            result=result,
            updated_at=datetime.now(UTC),
        )
    )
    _cleanup_upload(str(resolved_source))
