from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from langchain_qdrant.sparse_embeddings import SparseEmbeddings, SparseVector

_TOKEN_RE = re.compile(r"[a-z0-9_]+(?:[.-][a-z0-9_]+)*", re.IGNORECASE)


class LocalBM25SparseEmbeddings(SparseEmbeddings):
    """Build deterministic BM25-style exact-term vectors without a model call.

    Qdrant adds collection-level IDF. This class supplies stable term IDs and local term
    frequency. For example, ``HTTP 429 retry-after`` retains identifiers that dense semantic
    search might blur, giving exact technical tokens a second route into the candidate list.
    """

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        """Create sparse document vectors with logarithmically dampened term frequency."""
        return [self._embed(text, use_term_frequency=True) for text in texts]

    def embed_query(self, text: str) -> SparseVector:
        """Create a sparse query vector where each distinct requested term has weight one."""
        return self._embed(text, use_term_frequency=False)

    @staticmethod
    def _embed(text: str, *, use_term_frequency: bool) -> SparseVector:
        """Tokenize, weight, and order dimensions so output is deterministic and testable."""
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
    """Map the same token to the same unsigned 32-bit sparse dimension on every process."""
    digest = hashlib.blake2b(token.encode(), digest_size=4).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)
