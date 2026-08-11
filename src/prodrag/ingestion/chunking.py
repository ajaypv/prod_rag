from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

import numpy as np
from chonkie import SemanticChunker
from chonkie.embeddings import BaseEmbeddings
from langchain_core.embeddings import Embeddings


class ChunkingStrategy(Protocol):
    """Small interface that lets ingestion use semantic or test chunkers interchangeably."""
    def chunk(self, text: str) -> list[str]:
        """Split one parent section into ordered, non-empty searchable children."""
        ...


class OCIChonkieEmbeddings(BaseEmbeddings):
    """Adapt LangChain OCI embeddings to Chonkie's NumPy-based contract.

    Chonkie asks for NumPy arrays and token counts; LangChain returns Python float lists. This
    adapter performs that translation while preserving ``SEARCH_DOCUMENT`` embedding behavior.
    """

    def __init__(self, embeddings: Embeddings, dimension: int) -> None:
        self._embeddings = embeddings
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        """Report the configured OCI vector width so Chonkie can validate its arrays."""
        return self._dimension

    def embed(self, text: str) -> np.ndarray:
        """Embed one sentence/window as document text for a boundary decision."""
        return np.asarray(self._embeddings.embed_documents([text])[0], dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Batch boundary embeddings into fewer OCI requests when Chonkie provides a list."""
        if not texts:
            return []
        return [
            np.asarray(vector, dtype=np.float32)
            for vector in self._embeddings.embed_documents(texts)
        ]

    def count_tokens(self, text: str) -> int:
        """Estimate tokens conservatively; OCI performs final provider-side tokenization."""
        # A deterministic conservative counter; OCI applies its own final tokenization.
        return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))

    def count_tokens_batch(self, texts: list[str]) -> list[int]:
        """Apply the same deterministic estimate to every candidate fragment."""
        return [self.count_tokens(text) for text in texts]

    def get_tokenizer(self) -> Callable[[str], int]:
        """Give Chonkie the callable it uses while enforcing the 450-token target."""
        return self.count_tokens

    @classmethod
    def is_available(cls) -> bool:
        """The adapter needs no optional local model beyond the configured OCI client."""
        return True

    def __repr__(self) -> str:
        """Show useful non-secret diagnostic information in logs and test failures."""
        return f"OCIChonkieEmbeddings(dimension={self.dimension})"


class SemanticChunkingStrategy:
    """Split each parent when neighboring sentence windows change topic.

    Example: token-rotation prerequisites and rotation steps are likely grouped, while a sudden
    billing paragraph has lower semantic similarity and starts a new child. ``chunk_size`` is a
    target/cap and ``threshold`` controls sensitivity to those semantic changes.
    """
    def __init__(
        self,
        embeddings: Embeddings,
        *,
        dimension: int,
        chunk_size: int = 450,
        threshold: float = 0.72,
    ) -> None:
        adapter = OCIChonkieEmbeddings(embeddings, dimension)
        # The sliding sentence window helps the semantic boundary decision without
        # copying a fixed overlap into every stored child chunk.
        self._chunker = SemanticChunker(
            embedding_model=adapter,
            threshold=threshold,
            chunk_size=chunk_size,
            similarity_window=3,
            min_sentences_per_chunk=1,
            delim=[". ", "! ", "? ", "\n\n"],
            include_delim="prev",
        )

    def chunk(self, text: str) -> list[str]:
        """Return non-empty child text and preserve the source if Chonkie returns nothing."""
        chunks = self._chunker.chunk(text)
        output = [chunk.text.strip() for chunk in chunks if chunk.text.strip()]
        # Preserve non-empty source text if the third-party chunker yields no chunks.
        return output or [text.strip()]
