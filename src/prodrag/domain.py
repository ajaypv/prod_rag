from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Normalized local document after every supported format has become Markdown."""
    source_path: Path
    title: str
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParentSection:
    """Heading-aware context block stored with every searchable child.

    Example: a ``Troubleshooting > Authentication`` section can contain several 450-token
    children. Search matches a child; answer generation later receives this complete parent.
    """
    section_id: str
    heading: str
    text: str
    order: int


@dataclass(frozen=True, slots=True)
class RetrievedCandidate:
    """One retrieved LangChain document plus its first- and second-stage scores."""
    document: Document
    hybrid_score: float
    rerank_score: float | None = None

    @property
    def final_score(self) -> float:
        """Prefer OCI rerank relevance; fall back to Qdrant's RRF score when not reranked."""
        return self.rerank_score if self.rerank_score is not None else self.hybrid_score
