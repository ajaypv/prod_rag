from typing import Protocol

from prodrag.domain import RetrievedCandidate


class HybridSearcher(Protocol):
    """Contract for dense-and-sparse retrieval implementations."""

    def hybrid_search(
        self,
        query: str,
        *,
        tenant_id: str,
        product: str | None,
        version: str | None,
        limit: int,
    ) -> list[RetrievedCandidate]: ...
