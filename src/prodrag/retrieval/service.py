from __future__ import annotations

import logging
import time
import uuid

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.flow import FlowCallback, emit_flow_event
from prodrag.models import FlowStatus
from prodrag.retrieval.context import ParentContextAssembler
from prodrag.retrieval.hybrid_search import HybridSearcher
from prodrag.retrieval.reranking import Reranker

logger = logging.getLogger("prodrag.retrieval")


class RetrievalService:
    """Orchestrate hybrid retrieval, reranking, filtering, and parent expansion."""

    def __init__(
        self,
        settings: Settings,
        hybrid_searcher: HybridSearcher,
        reranker: Reranker | None,
        context_assembler: ParentContextAssembler,
    ) -> None:
        self.settings = settings
        self.hybrid_searcher = hybrid_searcher
        self.reranker = reranker
        self.context_assembler = context_assembler

    def retrieve(
        self,
        query: str,
        *,
        tenant_id: str,
        product: str | None = None,
        version: str | None = None,
        request_id: str | None = None,
        on_stage: FlowCallback | None = None,
    ) -> list[RetrievedCandidate]:
        request_id = request_id or str(uuid.uuid4())
        started = time.perf_counter()
        hybrid_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="hybrid_retrieval",
            status=FlowStatus.RUNNING,
            message="Running dense vector and BM25 retrieval with RRF fusion",
            data={"candidate_limit": self.settings.retrieval_candidates},
        )
        candidates = self.hybrid_searcher.hybrid_search(
            query,
            tenant_id=tenant_id,
            product=product,
            version=version,
            limit=self.settings.retrieval_candidates,
        )
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="hybrid_retrieval",
            status=FlowStatus.COMPLETED,
            message="Hybrid retrieval candidates returned",
            duration_ms=(time.perf_counter() - hybrid_started) * 1_000,
            data={"candidate_count": len(candidates)},
        )

        rerank_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="rerank",
            status=(FlowStatus.RUNNING if self.reranker else FlowStatus.SKIPPED),
            message=(
                "Reranking fused candidates with the configured relevance model"
                if self.reranker
                else "Reranking is disabled; preserving the fused RRF order"
            ),
        )
        candidates = self._rerank_and_filter(query, candidates)
        if self.reranker:
            emit_flow_event(
                on_stage,
                operation_id=request_id,
                stage="rerank",
                status=FlowStatus.COMPLETED,
                message="Candidate order refined and low-scoring results removed",
                duration_ms=(time.perf_counter() - rerank_started) * 1_000,
                data={"candidate_count": len(candidates)},
            )

        context_started = time.perf_counter()
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="context",
            status=FlowStatus.RUNNING,
            message="Expanding child hits into unique parent contexts",
        )
        contexts = self.context_assembler.assemble(candidates)
        emit_flow_event(
            on_stage,
            operation_id=request_id,
            stage="context",
            status=FlowStatus.COMPLETED,
            message="Final parent evidence assembled",
            duration_ms=(time.perf_counter() - context_started) * 1_000,
            data={
                "context_count": len(contexts),
                "scores": [round(item.final_score, 6) for item in contexts],
            },
        )
        logger.info(
            "retrieval_completed",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "product": product,
                "version": version,
                "candidate_count": len(contexts),
                "retrieval_scores": [round(item.final_score, 6) for item in contexts],
                "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
            },
        )
        return contexts

    def _rerank_and_filter(
        self, query: str, candidates: list[RetrievedCandidate]
    ) -> list[RetrievedCandidate]:
        if self.reranker is None:
            return candidates

        reranked = self.reranker.rerank(
            query,
            candidates,
            top_n=self.settings.final_contexts * 2,
        )
        return [
            candidate
            for candidate in reranked
            if candidate.final_score >= self.settings.min_rerank_score
        ]
