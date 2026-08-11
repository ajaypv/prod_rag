from __future__ import annotations

from functools import lru_cache

from prodrag.answering import GroundedAnswerService
from prodrag.clients import get_chat_model, get_embeddings, get_native_oci_client
from prodrag.config import get_settings
from prodrag.ingestion import IngestionService
from prodrag.ingestion.chunking import SemanticChunkingStrategy
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner
from prodrag.jobs import RedisJobStore
from prodrag.querying import QueryService
from prodrag.retrieval import RetrievalService
from prodrag.retrieval.confidence import ScoreThresholdConfidenceGrader
from prodrag.retrieval.context import ParentContextAssembler
from prodrag.retrieval.reranking import OCIReranker
from prodrag.triage import TicketTriageService
from prodrag.vector_store import QdrantIndex


@lru_cache(maxsize=1)
def get_index() -> QdrantIndex:
    return QdrantIndex(get_settings(), get_embeddings())


@lru_cache(maxsize=1)
def get_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(
        parser=DoclingParser(
            max_file_bytes=settings.max_file_bytes,
            max_pages=settings.max_pdf_pages,
            pdf_ocr_enabled=settings.pdf_ocr_enabled,
            pdf_table_structure_enabled=settings.pdf_table_structure_enabled,
            pdf_force_backend_text=settings.pdf_force_backend_text,
        ),
        sectioner=MarkdownSectioner(settings.parent_max_chars),
        chunker=SemanticChunkingStrategy(
            get_embeddings(),
            dimension=settings.oci_embed_dimension,
            chunk_size=settings.chunk_size_tokens,
            threshold=settings.semantic_threshold,
        ),
        index=get_index(),
    )


@lru_cache(maxsize=1)
def get_retrieval_service() -> RetrievalService:
    settings = get_settings()
    reranker = None
    if settings.oci_rerank_enabled:
        if not settings.oci_compartment_id:
            raise RuntimeError("OCI_COMPARTMENT_OCID is required when reranking is enabled")
        reranker = OCIReranker(
            get_native_oci_client(),
            compartment_id=settings.oci_compartment_id,
            model_id=settings.oci_rerank_model,
        )
    return RetrievalService(
        settings,
        get_index(),
        reranker,
        ParentContextAssembler(limit=settings.final_contexts),
    )


@lru_cache(maxsize=1)
def get_triage_service() -> TicketTriageService:
    return TicketTriageService(
        get_chat_model(), retry_attempts=get_settings().model_retry_attempts
    )


@lru_cache(maxsize=1)
def get_answer_service() -> GroundedAnswerService:
    return GroundedAnswerService(
        get_settings(),
        get_chat_model(),
        ScoreThresholdConfidenceGrader(get_settings()),
    )


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    return QueryService(
        get_retrieval_service(),
        get_answer_service(),
        get_triage_service(),
    )


@lru_cache(maxsize=1)
def get_job_store() -> RedisJobStore:
    settings = get_settings()
    return RedisJobStore(settings.redis_url, ttl_seconds=settings.job_ttl_seconds)
