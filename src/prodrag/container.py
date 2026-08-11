from __future__ import annotations

from functools import lru_cache

from prodrag.answering import GroundedAnswerService
from prodrag.clients import get_chat_model, get_embeddings, get_native_oci_client
from prodrag.config import get_settings
from prodrag.ingestion import IngestionService
from prodrag.ingestion.chunking import SemanticChunkingStrategy
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner
from prodrag.querying import QueryService
from prodrag.retrieval import RetrievalService
from prodrag.retrieval.confidence import ScoreThresholdConfidenceGrader
from prodrag.retrieval.context import ParentContextAssembler
from prodrag.retrieval.reranking import OCIReranker
from prodrag.triage import TicketTriageService
from prodrag.vector_store import QdrantIndex


@lru_cache(maxsize=1)
def get_index() -> QdrantIndex:
    """Build the shared local vector index used by both ingestion and querying.

    ``QdrantIndex`` receives the asymmetric OCI embedding adapter: document ingestion calls
    ``embed_documents`` while retrieval calls ``embed_query``. Caching here prevents opening
    a second embedded Qdrant instance in the same CLI process.
    """
    return QdrantIndex(get_settings(), get_embeddings())


@lru_cache(maxsize=1)
def get_ingestion_service() -> IngestionService:
    """Connect the complete CLI ingestion chain.

    Flow: local file -> Docling/UTF-8 parsing -> heading parents -> semantic children ->
    OCI document embeddings -> local Qdrant. The returned service owns orchestration only;
    each injected component keeps one focused responsibility and can be tested separately.
    """
    settings = get_settings()
    return IngestionService(
        parser=DoclingParser(max_file_bytes=settings.max_file_bytes),
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
    """Connect hybrid Qdrant search, optional OCI reranking, and parent expansion.

    With defaults, Qdrant produces 20 fused child candidates, OCI reranks up to 10, and the
    assembler returns at most 5 distinct parent sections. If reranking is disabled, hybrid
    RRF scores become the final scores used by the confidence gate.
    """
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
    """Create the safety classifier that runs before a query can reach retrieval."""
    return TicketTriageService(get_chat_model())


@lru_cache(maxsize=1)
def get_answer_service() -> GroundedAnswerService:
    """Create answer generation with a local retrieval-confidence gate."""
    return GroundedAnswerService(
        get_settings(),
        get_chat_model(),
        ScoreThresholdConfidenceGrader(get_settings()),
    )


@lru_cache(maxsize=1)
def get_query_service() -> QueryService:
    """Create the top-level service called by ``prodrag query``.

    This is the query composition boundary: triage runs first, retrieval runs only for safe
    questions, and grounded answering runs only when retrieved evidence is strong enough.
    """
    return QueryService(
        get_retrieval_service(),
        get_answer_service(),
        get_triage_service(),
    )
