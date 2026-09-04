from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from prodrag.config import get_settings
from prodrag.container import get_ingestion_service, get_job_store
from prodrag.flow import emit_flow_event
from prodrag.models import (
    EvaluationJobStatus,
    EvaluationStage,
    FlowEvent,
    FlowStatus,
    JobState,
    JobStatus,
)
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
            stage=previous.stage if previous else "failed",
            message=(
                f"{detail}; retries exhausted after "
                f"{retry_metadata.get('retries', 0)} attempts"
            ),
            events=previous.events if previous else [],
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

    previous = job_store.get(job_id)
    events = list(previous.events) if previous else []

    def record(event: FlowEvent) -> None:
        events.append(event)
        job_store.put(
            JobStatus(
                job_id=job_id,
                state=JobState.RUNNING,
                document_id=document_id,
                tenant_id=tenant_id,
                stage=event.stage,
                message=event.message,
                events=list(events),
                updated_at=datetime.now(UTC),
            )
        )

    job_store.put(
        JobStatus(
            job_id=job_id,
            state=JobState.RUNNING,
            document_id=document_id,
            tenant_id=tenant_id,
            stage=previous.stage if previous else "queued",
            events=events,
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
            operation_id=job_id,
            on_stage=record,
        )
    except Exception as exc:
        # Dramatiq will retry with exponential backoff; a later attempt overwrites this state.
        current = job_store.get(job_id)
        job_store.put(
            (current or JobStatus(
                job_id=job_id,
                state=JobState.RETRYING,
                document_id=document_id,
                tenant_id=tenant_id,
            )).model_copy(
                update={
                    "state": JobState.RETRYING,
                    "message": f"{type(exc).__name__}: {exc}",
                    "updated_at": datetime.now(UTC),
                }
            )
        )
        raise
    emit_flow_event(
        record,
        operation_id=job_id,
        stage="complete",
        status=FlowStatus.COMPLETED,
        message="Document ingestion completed",
        data={
            "parents_indexed": result.parents_indexed,
            "chunks_indexed": result.chunks_indexed,
        },
    )
    job_store.put(
        JobStatus(
            job_id=job_id,
            state=JobState.SUCCEEDED,
            document_id=document_id,
            tenant_id=tenant_id,
            stage="complete",
            result=result,
            events=events,
            updated_at=datetime.now(UTC),
        )
    )
    _cleanup_upload(str(resolved_source))


def _cleanup_evaluation(source_path: str) -> None:
    evaluation_root = (settings.data_dir / "evaluations").resolve()
    source = Path(source_path).resolve()
    if not source.is_relative_to(evaluation_root):
        return
    source.unlink(missing_ok=True)


@dramatiq.actor(queue_name="evaluation", max_retries=0, time_limit=3_600_000)
def evaluate_dataset(
    job_id: str,
    source_path: str,
    tenant_id: str,
    end_to_end: bool,
    deep_eval: bool,
) -> None:
    """Run an uploaded golden dataset outside the API process and retain progress in Redis."""
    from prodrag.evaluation import RAGEvaluationRecord, evaluate, evaluate_answers, load_cases

    job_store = get_job_store()
    previous = job_store.get_evaluation(job_id)
    events = list(previous.events) if previous else []
    current_stage = EvaluationStage.QUEUED

    def record(event: FlowEvent) -> None:
        nonlocal current_stage
        current_stage = EvaluationStage(event.stage)
        events.append(event)
        job_store.put_evaluation(
            EvaluationJobStatus(
                job_id=job_id,
                state=JobState.RUNNING,
                tenant_id=tenant_id,
                stage=current_stage,
                deep_eval=deep_eval,
                message=event.message,
                events=list(events),
                updated_at=datetime.now(UTC),
            )
        )

    def stage_started(stage: EvaluationStage, message: str) -> None:
        emit_flow_event(
            record,
            operation_id=job_id,
            stage=stage.value,
            status=FlowStatus.RUNNING,
            message=message,
        )

    def stage_completed(
        stage: EvaluationStage,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        emit_flow_event(
            record,
            operation_id=job_id,
            stage=stage.value,
            status=FlowStatus.COMPLETED,
            message=message,
            data=data,
        )

    try:
        source = Path(source_path).resolve(strict=True)
        evaluation_root = (settings.data_dir / "evaluations").resolve()
        if not source.is_relative_to(evaluation_root):
            raise ValueError("Evaluation source is outside the configured evaluation directory")

        stage_started(EvaluationStage.LOAD_DATASET, "Validating the uploaded golden dataset")
        cases = load_cases(source)
        if any(case.tenant_id != tenant_id for case in cases):
            raise ValueError("Every evaluation case must match the authorized tenant")
        stage_completed(
            EvaluationStage.LOAD_DATASET,
            "Golden dataset loaded",
            {"question_count": len(cases)},
        )

        stage_started(EvaluationStage.RETRIEVAL, "Measuring retrieval recall and precision")
        metrics: dict[str, object] = evaluate(cases)
        stage_completed(
            EvaluationStage.RETRIEVAL,
            "Retrieval metrics calculated",
            {
                "recall": metrics.get("mean_recall"),
                "precision": metrics.get("mean_precision"),
            },
        )

        records: list[RAGEvaluationRecord] = []
        if end_to_end:
            stage_started(
                EvaluationStage.ANSWER_QUALITY,
                "Running answer, citation, and abstention evaluation",
            )
            metrics.update(
                evaluate_answers(
                    cases,
                    records=records if deep_eval else None,
                )
            )
            stage_completed(
                EvaluationStage.ANSWER_QUALITY,
                "End-to-end answer metrics calculated",
                {"quality_labeled_questions": metrics.get("quality_labeled_questions")},
            )
        else:
            emit_flow_event(
                record,
                operation_id=job_id,
                stage=EvaluationStage.ANSWER_QUALITY.value,
                status=FlowStatus.SKIPPED,
                message="End-to-end answer evaluation was not requested",
            )

        if deep_eval:
            stage_started(EvaluationStage.DEEPEVAL, "Running DeepEval RAG judge metrics")
            from prodrag.clients import get_chat_model
            from prodrag.deepeval_evaluation import OCIChatDeepEvalModel, evaluate_deepeval

            judge = OCIChatDeepEvalModel(
                get_chat_model(),
                model_name=settings.oci_chat_model,
                retry_attempts=settings.model_retry_attempts,
            )
            metrics.update(evaluate_deepeval(records, judge))
            stage_completed(
                EvaluationStage.DEEPEVAL,
                "DeepEval metrics calculated",
                {"labeled_questions": metrics.get("deepeval_labeled_questions")},
            )
        else:
            emit_flow_event(
                record,
                operation_id=job_id,
                stage=EvaluationStage.DEEPEVAL.value,
                status=FlowStatus.SKIPPED,
                message="DeepEval was not requested",
            )

        stage_started(EvaluationStage.REPORT, "Preparing the evaluation report")
        stage_completed(EvaluationStage.REPORT, "Evaluation report is ready")
        job_store.put_evaluation(
            EvaluationJobStatus(
                job_id=job_id,
                state=JobState.SUCCEEDED,
                tenant_id=tenant_id,
                stage=EvaluationStage.REPORT,
                deep_eval=deep_eval,
                message="Evaluation completed",
                metrics=metrics,
                events=events,
                updated_at=datetime.now(UTC),
            )
        )
    except Exception as exc:
        job_store.put_evaluation(
            EvaluationJobStatus(
                job_id=job_id,
                state=JobState.FAILED,
                tenant_id=tenant_id,
                stage=current_stage,
                deep_eval=deep_eval,
                message=f"{type(exc).__name__}: {exc}",
                events=events,
                updated_at=datetime.now(UTC),
            )
        )
    finally:
        _cleanup_evaluation(source_path)
