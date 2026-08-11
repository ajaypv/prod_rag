from typing import Protocol

from prodrag.domain import RetrievedCandidate


class HybridSearcher(Protocol):
    """Retrieval contract implemented by Qdrant and lightweight test doubles.

    This boundary lets ``RetrievalService`` tests exercise orchestration without starting a
    database or calling OCI embeddings.
    """
    """Contract for dense-and-sparse retrieval implementations."""

    def hybrid_search(
        self,
        query: str,
        *,
        tenant_id: str,
        product: str | None,
        version: str | None,
        limit: int,
    ) -> list[RetrievedCandidate]:
        """Return fused child candidates constrained by the supplied metadata filters."""
        ...
