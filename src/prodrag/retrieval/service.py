from __future__ import annotations

import logging
import time
import uuid

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
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
    ) -> list[RetrievedCandidate]:
        request_id = request_id or str(uuid.uuid4())
        started = time.perf_counter()
        candidates = self.hybrid_searcher.hybrid_search(
            query,
            tenant_id=tenant_id,
            product=product,
            version=version,
            limit=self.settings.retrieval_candidates,
        )
        candidates = self._rerank_and_filter(query, candidates)
        contexts = self.context_assembler.assemble(candidates)
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
