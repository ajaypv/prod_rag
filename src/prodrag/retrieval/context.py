from collections.abc import Sequence

from prodrag.domain import RetrievedCandidate
from prodrag.parent_store import ParentNotFoundError, ParentStore, StoredParent
from prodrag.tokenization import TokenCounter, conservative_token_count


class ParentContextAssembler:
    """Deduplicate child hits and replace each winner with its durable parent text.

    Qdrant returns small child chunks because they are more precise search targets.
    The answer model needs the surrounding section, so this class follows the
    ``parent_id`` reference into the local parent store after ranking has finished.
    """

    def __init__(
        self,
        parent_store: ParentStore,
        *,
        limit: int,
        neighbor_count: int = 1,
        expanded_max_tokens: int = 3_000,
        token_counter: TokenCounter = conservative_token_count,
    ) -> None:
        self.parent_store = parent_store
        self.limit = limit
        self.neighbor_count = neighbor_count
        self.expanded_max_tokens = expanded_max_tokens
        self._count_tokens = token_counter

    def assemble(self, candidates: Sequence[RetrievedCandidate]) -> list[RetrievedCandidate]:
        contexts: list[RetrievedCandidate] = []
        # parent_id values are only unique inside a document. Include tenant and
        # document so two guides with a section named "Introduction" cannot collapse.
        seen_parents: set[tuple[str, str, str]] = set()

        for candidate in candidates:
            metadata = candidate.document.metadata
            tenant_id = str(metadata.get("tenant_id", ""))
            document_id = str(metadata.get("document_id", ""))
            parent_id = str(metadata.get("parent_id", ""))
            parent_key = (tenant_id, document_id, parent_id)
            if parent_key in seen_parents:
                continue
            seen_parents.add(parent_key)

            parent = self.parent_store.get_parent(
                tenant_id=tenant_id,
                document_id=document_id,
                parent_id=parent_id,
            )
            if parent is not None:
                expanded = self._expand_parent(
                    parent,
                    excluded_parent_keys=seen_parents - {parent_key},
                )
                parent_text = "\n\n".join(item.text for item in expanded)
                for item in expanded:
                    seen_parents.add((item.tenant_id, item.document_id, item.parent_id))
                expanded_parent_ids = [item.parent_id for item in expanded]
            else:
                # Temporary migration path for Qdrant points written before parents
                # moved to SQLite. Reingesting a document removes this dependency.
                parent_text = metadata.get("parent_text")
                if not parent_text:
                    raise ParentNotFoundError(
                        "Retrieved child references a missing parent: "
                        f"tenant={tenant_id!r}, document={document_id!r}, "
                        f"parent={parent_id!r}. Reingest the document."
                    )
                expanded_parent_ids = [parent_id]

            candidate = RetrievedCandidate(
                document=candidate.document.model_copy(
                    update={
                        "page_content": str(parent_text),
                        "metadata": {
                            **metadata,
                            "expanded_parent_ids": expanded_parent_ids,
                        },
                    }
                ),
                hybrid_score=candidate.hybrid_score,
                rerank_score=candidate.rerank_score,
            )

            contexts.append(candidate)
            if len(contexts) >= self.limit:
                break

        return contexts

    def _expand_parent(
        self,
        parent: StoredParent,
        *,
        excluded_parent_keys: set[tuple[str, str, str]],
    ) -> list[StoredParent]:
        """Add complete adjacent parts while staying inside the expansion token budget."""
        previous: list[StoredParent] = []
        following: list[StoredParent] = []
        previous_id = parent.previous_parent_id
        next_id = parent.next_parent_id

        for _ in range(self.neighbor_count):
            if previous_id:
                item = self.parent_store.get_parent(
                    tenant_id=parent.tenant_id,
                    document_id=parent.document_id,
                    parent_id=previous_id,
                )
                item_key = self._parent_key(item) if item is not None else None
                if (
                    item is not None
                    and item_key not in excluded_parent_keys
                    and self._fits_expansion([item, *reversed(previous), parent, *following])
                ):
                    previous.append(item)
                    previous_id = item.previous_parent_id
                else:
                    previous_id = None

            if next_id:
                item = self.parent_store.get_parent(
                    tenant_id=parent.tenant_id,
                    document_id=parent.document_id,
                    parent_id=next_id,
                )
                item_key = self._parent_key(item) if item is not None else None
                if (
                    item is not None
                    and item_key not in excluded_parent_keys
                    and self._fits_expansion([*reversed(previous), parent, *following, item])
                ):
                    following.append(item)
                    next_id = item.next_parent_id
                else:
                    next_id = None

        return [*reversed(previous), parent, *following]

    def _fits_expansion(self, parents: list[StoredParent]) -> bool:
        return self._count_tokens("\n\n".join(parent.text for parent in parents)) <= (
            self.expanded_max_tokens
        )

    @staticmethod
    def _parent_key(parent: StoredParent) -> tuple[str, str, str]:
        return parent.tenant_id, parent.document_id, parent.parent_id
