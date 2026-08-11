from collections.abc import Sequence

from prodrag.domain import RetrievedCandidate


class ParentContextAssembler:
    """Deduplicate child matches and expand each winner to its parent section.

    Three high-scoring children from ``Authentication > Token rotation`` count as one final
    context. The first/highest-ranked child fixes its position and ``parent_text`` supplies the
    complete evidence passed to answer generation.
    """

    def __init__(self, *, limit: int) -> None:
        self.limit = limit

    def assemble(
        self, candidates: Sequence[RetrievedCandidate]
    ) -> list[RetrievedCandidate]:
        """Return at most ``limit`` unique parents while preserving relevance order."""
        contexts: list[RetrievedCandidate] = []
        seen_parents: set[str] = set()

        for candidate in candidates:
            parent_id = str(candidate.document.metadata.get("parent_id", ""))
            # Multiple child chunks can point to one section; retain only its best-ranked hit.
            if parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)

            parent_text = candidate.document.metadata.get("parent_text")
            if parent_text:
                # Keep the child's scores and citation metadata while giving the answer model
                # the complete parent section as grounded context.
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
