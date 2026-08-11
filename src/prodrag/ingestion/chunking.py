from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

import numpy as np
from chonkie import SemanticChunker
from chonkie.embeddings import BaseEmbeddings
from langchain_core.embeddings import Embeddings


class ChunkingStrategy(Protocol):
    def chunk(self, text: str) -> list[str]: ...


class OCIChonkieEmbeddings(BaseEmbeddings):
    """Adapt LangChain OCI embeddings to Chonkie's semantic chunker contract."""

    def __init__(self, embeddings: Embeddings, dimension: int) -> None:
        self._embeddings = embeddings
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> np.ndarray:
        return np.asarray(self._embeddings.embed_documents([text])[0], dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        return [
            np.asarray(vector, dtype=np.float32)
            for vector in self._embeddings.embed_documents(texts)
        ]

    def count_tokens(self, text: str) -> int:
        # A deterministic conservative counter; OCI applies its own final tokenization.
        return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))

    def count_tokens_batch(self, texts: list[str]) -> list[int]:
        return [self.count_tokens(text) for text in texts]

    def get_tokenizer(self) -> Callable[[str], int]:
        return self.count_tokens

    @classmethod
    def is_available(cls) -> bool:
        return True

    def __repr__(self) -> str:
        return f"OCIChonkieEmbeddings(dimension={self.dimension})"


class SemanticChunkingStrategy:
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
        chunks = self._chunker.chunk(text)
        output = [chunk.text.strip() for chunk in chunks if chunk.text.strip()]
        # Preserve non-empty source text if the third-party chunker yields no chunks.
        return output or [text.strip()]
