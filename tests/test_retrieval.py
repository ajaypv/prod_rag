from langchain_core.documents import Document

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.retrieval import RetrievalService
from prodrag.retrieval.context import ParentContextAssembler


class FakeIndex:
    def hybrid_search(self, *args, **kwargs):
        return [
            RetrievedCandidate(
                Document(
                    page_content="child one",
                    metadata={"parent_id": "p1", "parent_text": "full parent one"},
                ),
                hybrid_score=0.5,
            ),
            RetrievedCandidate(
                Document(
                    page_content="child two",
                    metadata={"parent_id": "p1", "parent_text": "full parent one"},
                ),
                hybrid_score=0.4,
            ),
            RetrievedCandidate(
                Document(
                    page_content="child three",
                    metadata={"parent_id": "p2", "parent_text": "full parent two"},
                ),
                hybrid_score=0.3,
            ),
        ]


class FakeReranker:
    def rerank(self, query, candidates, *, top_n):
        scores = [0.9, 0.8, 0.1]
        return [
            RetrievedCandidate(item.document, item.hybrid_score, score)
            for item, score in zip(candidates, scores, strict=True)
        ]


def test_retrieval_filters_low_scores_deduplicates_and_expands_parents() -> None:
    settings = Settings(
        _env_file=None,
        min_rerank_score=0.15,
        final_contexts=5,
    )
    index = FakeIndex()
    service = RetrievalService(
        settings,
        index,  # type: ignore[arg-type]
        FakeReranker(),
        ParentContextAssembler(limit=settings.final_contexts),
    )

    results = service.retrieve("reset password", tenant_id="default")

    assert len(results) == 1
    assert results[0].document.page_content == "full parent one"
    assert results[0].final_score == 0.9
    assert index.hybrid_search("reset password")[0].document.page_content == "child one"
