from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source_path: Path
    title: str
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParentSection:
    section_id: str
    heading: str
    text: str
    order: int


@dataclass(frozen=True, slots=True)
class RetrievedCandidate:
    document: Document
    hybrid_score: float
    rerank_score: float | None = None

    @property
    def final_score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.hybrid_score

