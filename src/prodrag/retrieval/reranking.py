from collections.abc import Sequence
from typing import Protocol

from prodrag.domain import RetrievedCandidate


class Reranker(Protocol):
    def rerank(
        self, query: str, candidates: Sequence[RetrievedCandidate], *, top_n: int
    ) -> list[RetrievedCandidate]: ...


class OCIReranker:
    """Reorder hybrid candidates using an OCI on-demand rerank model."""

    def __init__(self, client, *, compartment_id: str, model_id: str) -> None:
        self.client = client
        self.compartment_id = compartment_id
        self.model_id = model_id

    def rerank(
        self, query: str, candidates: Sequence[RetrievedCandidate], *, top_n: int
    ) -> list[RetrievedCandidate]:
        if not candidates:
            return []

        from oci.generative_ai_inference import models

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
                document=candidates[item.index].document,
                hybrid_score=candidates[item.index].hybrid_score,
                rerank_score=float(item.relevance_score),
            )
            for item in response.data.document_ranks
        ]
