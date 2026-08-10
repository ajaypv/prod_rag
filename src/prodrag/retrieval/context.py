from collections.abc import Sequence

from prodrag.domain import RetrievedCandidate


class ParentContextAssembler:
    """Deduplicate child matches and expand each winner to its parent section."""

    def __init__(self, *, limit: int) -> None:
        self.limit = limit

    def assemble(
        self, candidates: Sequence[RetrievedCandidate]
    ) -> list[RetrievedCandidate]:
        contexts: list[RetrievedCandidate] = []
        seen_parents: set[str] = set()

        for candidate in candidates:
            parent_id = str(candidate.document.metadata.get("parent_id", ""))
            if parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)

            parent_text = candidate.document.metadata.get("parent_text")
            if parent_text:
                candidate = RetrievedCandidate(
                    document=candidate.document.model_copy(
                        update={"page_content": str(parent_text)}
                    ),
                    hybrid_score=candidate.hybrid_score,
                    rerank_score=candidate.rerank_score,
                )

            contexts.append(candidate)
            if len(contexts) >= self.limit:
                break

        return contexts
