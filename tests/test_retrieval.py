from langchain_core.documents import Document

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import FlowStatus
from prodrag.parent_store import StoredParent
from prodrag.retrieval import RetrievalService
from prodrag.retrieval.context import ParentContextAssembler


class FakeIndex:
    def hybrid_search(self, *args, **kwargs):
        return [
            RetrievedCandidate(
                Document(
                    page_content="child one",
                    metadata={
                        "tenant_id": "default",
                        "document_id": "guide",
                        "parent_id": "p1",
                    },
                ),
                hybrid_score=0.5,
            ),
            RetrievedCandidate(
                Document(
                    page_content="child two",
                    metadata={
                        "tenant_id": "default",
                        "document_id": "guide",
                        "parent_id": "p1",
                    },
                ),
                hybrid_score=0.4,
            ),
            RetrievedCandidate(
                Document(
                    page_content="child three",
                    metadata={
                        "tenant_id": "default",
                        "document_id": "guide",
                        "parent_id": "p2",
                    },
                ),
                hybrid_score=0.3,
            ),
        ]


class FakeParentStore:
    def get_parent(self, *, tenant_id, document_id, parent_id):
        texts = {"p1": "full parent one", "p2": "full parent two"}
        text = texts.get(parent_id)
        if text is None:
            return None
        return StoredParent(
            tenant_id=tenant_id,
            document_id=document_id,
            parent_id=parent_id,
            checksum="checksum",
            heading="Section",
            text=text,
            section_order=0,
            product=None,
            version=None,
        )


class LinkedParentStore:
    def __init__(self) -> None:
        self.parents = {
            "p1": self._parent("p1", "parent part one", 1, None, "p2"),
            "p2": self._parent("p2", "parent part two", 2, "p1", "p3"),
            "p3": self._parent("p3", "parent part three", 3, "p2", None),
        }

    @staticmethod
    def _parent(parent_id, text, part, previous_id, next_id):
        return StoredParent(
            tenant_id="default",
            document_id="guide",
            parent_id=parent_id,
            checksum="checksum",
            heading="Large section",
            text=text,
            section_order=part - 1,
            product=None,
            version=None,
            part=part,
            part_count=3,
            previous_parent_id=previous_id,
            next_parent_id=next_id,
        )

    def get_parent(self, *, tenant_id, document_id, parent_id):
        assert tenant_id == "default"
        assert document_id == "guide"
        return self.parents.get(parent_id)


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
        ParentContextAssembler(FakeParentStore(), limit=settings.final_contexts),
    )

    events = []
    results = service.retrieve(
        "reset password",
        tenant_id="default",
        request_id="request-1",
        on_stage=events.append,
    )

    assert len(results) == 1
    assert results[0].document.page_content == "full parent one"
    assert results[0].final_score == 0.9
    assert index.hybrid_search("reset password")[0].document.page_content == "child one"
    completed = [event for event in events if event.status == FlowStatus.COMPLETED]
    assert [event.stage for event in completed] == [
        "hybrid_retrieval",
        "rerank",
        "context",
    ]
    assert completed[-1].data["context_count"] == 1


def test_parent_context_expands_adjacent_parts_and_deduplicates_them() -> None:
    candidates = [
        RetrievedCandidate(
            Document(
                page_content="matching child",
                metadata={
                    "tenant_id": "default",
                    "document_id": "guide",
                    "parent_id": "p2",
                },
            ),
            hybrid_score=0.9,
        ),
        RetrievedCandidate(
            Document(
                page_content="neighbor child",
                metadata={
                    "tenant_id": "default",
                    "document_id": "guide",
                    "parent_id": "p3",
                },
            ),
            hybrid_score=0.8,
        ),
    ]
    assembler = ParentContextAssembler(
        LinkedParentStore(),  # type: ignore[arg-type]
        limit=5,
        neighbor_count=1,
        expanded_max_tokens=100,
    )

    contexts = assembler.assemble(candidates)

    assert len(contexts) == 1
    assert contexts[0].document.page_content == (
        "parent part one\n\nparent part two\n\nparent part three"
    )
    assert contexts[0].document.metadata["expanded_parent_ids"] == ["p1", "p2", "p3"]


def test_parent_context_does_not_repeat_a_neighbor_in_later_context() -> None:
    candidates = [
        RetrievedCandidate(
            Document(
                page_content="first child",
                metadata={
                    "tenant_id": "default",
                    "document_id": "guide",
                    "parent_id": "p1",
                },
            ),
            hybrid_score=0.9,
        ),
        RetrievedCandidate(
            Document(
                page_content="third child",
                metadata={
                    "tenant_id": "default",
                    "document_id": "guide",
                    "parent_id": "p3",
                },
            ),
            hybrid_score=0.8,
        ),
    ]
    assembler = ParentContextAssembler(
        LinkedParentStore(),  # type: ignore[arg-type]
        limit=5,
        neighbor_count=1,
        expanded_max_tokens=100,
    )

    contexts = assembler.assemble(candidates)

    assert [context.document.metadata["expanded_parent_ids"] for context in contexts] == [
        ["p1", "p2"],
        ["p3"],
    ]
