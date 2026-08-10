from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from langchain_qdrant.sparse_embeddings import SparseEmbeddings, SparseVector

_TOKEN_RE = re.compile(r"[a-z0-9_]+(?:[.-][a-z0-9_]+)*", re.IGNORECASE)


class LocalBM25SparseEmbeddings(SparseEmbeddings):
    """Create deterministic sparse term vectors without downloading a model."""

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [self._embed(text, use_term_frequency=True) for text in texts]

    def embed_query(self, text: str) -> SparseVector:
        return self._embed(text, use_term_frequency=False)

    @staticmethod
    def _embed(text: str, *, use_term_frequency: bool) -> SparseVector:
        counts = Counter(_TOKEN_RE.findall(text.lower()))
        weighted = sorted(
            (
                _stable_index(token),
                1.0 + math.log(count) if use_term_frequency else 1.0,
            )
            for token, count in counts.items()
        )
        return SparseVector(
            indices=[item[0] for item in weighted],
            values=[item[1] for item in weighted],
        )


def _stable_index(token: str) -> int:
    digest = hashlib.blake2b(token.encode(), digest_size=4).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)
