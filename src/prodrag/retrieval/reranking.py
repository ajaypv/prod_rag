from collections.abc import Sequence
from typing import Protocol

from prodrag.domain import RetrievedCandidate


class Reranker(Protocol):
    """Second-stage relevance contract used by the retrieval orchestrator."""
    def rerank(
        self, query: str, candidates: Sequence[RetrievedCandidate], *, top_n: int
    ) -> list[RetrievedCandidate]:
        """Return at most ``top_n`` candidates ordered by query-to-passage relevance."""
        ...


class OCIReranker:
    """Reorder hybrid candidates using an OCI on-demand rerank model.

    RRF is broad but only knows rank positions. Reranking reads query and passage text. Two
    chunks mentioning "token" may rank similarly in Qdrant, while the chunk specifically about
    token *rotation* receives the higher cross-encoder relevance score.
    """

    def __init__(self, client, *, compartment_id: str, model_id: str) -> None:
        self.client = client
        self.compartment_id = compartment_id
        self.model_id = model_id

    def rerank(
        self, query: str, candidates: Sequence[RetrievedCandidate], *, top_n: int
    ) -> list[RetrievedCandidate]:
        """Send candidate text once, then map OCI result indexes back to source metadata."""
        if not candidates:
            return []

        from oci.generative_ai_inference import models

        # Reranking is intentionally limited to the locally retrieved candidate set; sending
        # the full corpus would increase latency, cost, and unnecessary data exposure.
        response = self.client.rerank_text(
            rerank_text_details=models.RerankTextDetails(
                input=query,
                compartment_id=self.compartment_id,
                serving_mode=models.OnDemandServingMode(model_id=self.model_id),
                documents=[candidate.document.page_content for candidate in candidates],
                top_n=min(top_n, len(candidates)),
                is_echo=False,
                max_tokens_per_document=2_000,
            )
        )
        return [
            RetrievedCandidate(
                # OCI returns the original candidate index, which preserves its document and
                # hybrid score while attaching the stronger cross-encoder relevance score.
                document=candidates[item.index].document,
                hybrid_score=candidates[item.index].hybrid_score,
                rerank_score=float(item.relevance_score),
            )
            for item in response.data.document_ranks
        ]
