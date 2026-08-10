from __future__ import annotations

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.retrieval.context import ParentContextAssembler
from prodrag.retrieval.hybrid_search import HybridSearcher
from prodrag.retrieval.reranking import Reranker


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
    ) -> list[RetrievedCandidate]:
        candidates = self.hybrid_searcher.hybrid_search(
            query,
            tenant_id=tenant_id,
            product=product,
            version=version,
            limit=self.settings.retrieval_candidates,
        )
        candidates = self._rerank_and_filter(query, candidates)
        return self.context_assembler.assemble(candidates)

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
