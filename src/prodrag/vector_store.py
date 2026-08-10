from __future__ import annotations

from collections.abc import Sequence

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.retrieval.sparse import LocalBM25SparseEmbeddings

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class QdrantIndex:
    """Local hybrid index with deterministic, idempotent document replacement."""

    def __init__(self, settings: Settings, embeddings: Embeddings) -> None:
        self.settings = settings
        api_key = (
            settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        )
        if settings.qdrant_path:
            qdrant_path = settings.qdrant_path.expanduser().resolve()
            qdrant_path.parent.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(qdrant_path))
        else:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=api_key or None,
                timeout=30,
            )
        self.sparse_embeddings = LocalBM25SparseEmbeddings()
        self.embeddings = embeddings
        self._store: QdrantVectorStore | None = None

    def _hnsw_config(self) -> models.HnswConfigDiff:
        return models.HnswConfigDiff(
            m=self.settings.qdrant_hnsw_m,
            ef_construct=self.settings.qdrant_hnsw_ef_construct,
        )

    def _search_params(self) -> models.SearchParams | None:
        if self.settings.qdrant_path:
            return None
        if self.settings.qdrant_hnsw_enabled:
            return models.SearchParams(
                exact=False,
                hnsw_ef=self.settings.qdrant_hnsw_ef_search,
            )
        return models.SearchParams(exact=True)

    def ensure_collection(self) -> None:
        collection_exists = self.client.collection_exists(self.settings.qdrant_collection)
        if not collection_exists:
            self.client.create_collection(
                collection_name=self.settings.qdrant_collection,
                vectors_config={
                    DENSE_VECTOR_NAME: models.VectorParams(
                        size=self.settings.oci_embed_dimension,
                        distance=models.Distance.COSINE,
                        on_disk=False,
                    )
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
                hnsw_config=(
                    self._hnsw_config() if self.settings.qdrant_hnsw_enabled else None
                ),
            )
        elif self.settings.qdrant_hnsw_enabled:
            self.client.update_collection(
                collection_name=self.settings.qdrant_collection,
                hnsw_config=self._hnsw_config(),
            )
        self._store = QdrantVectorStore(
            client=self.client,
            collection_name=self.settings.qdrant_collection,
            embedding=self.embeddings,
            sparse_embedding=self.sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name=DENSE_VECTOR_NAME,
            sparse_vector_name=SPARSE_VECTOR_NAME,
        )

    @property
    def store(self) -> QdrantVectorStore:
        if self._store is None:
            self.ensure_collection()
        assert self._store is not None
        return self._store

    def upsert_revision(
        self,
        documents: Sequence[Document],
        ids: Sequence[str],
        *,
        document_id: str,
        checksum: str,
        tenant_id: str,
    ) -> None:
        if len(documents) != len(ids):
            raise ValueError("documents and ids must have identical lengths")
        if not documents:
            raise ValueError("Refusing to replace a document with zero chunks")

        self.store.add_documents(documents=list(documents), ids=list(ids), batch_size=64)
        stale_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.document_id", match=models.MatchValue(value=document_id)
                ),
                models.FieldCondition(
                    key="metadata.tenant_id", match=models.MatchValue(value=tenant_id)
                ),
            ],
            must_not=[
                models.FieldCondition(
                    key="metadata.checksum", match=models.MatchValue(value=checksum)
                )
            ],
        )
        self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=models.FilterSelector(filter=stale_filter),
            wait=True,
        )

    def delete_document(self, document_id: str, *, tenant_id: str) -> None:
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.document_id", match=models.MatchValue(value=document_id)
                    ),
                    models.FieldCondition(
                        key="metadata.tenant_id", match=models.MatchValue(value=tenant_id)
                    ),
                ]
            )
        )
        self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=selector,
            wait=True,
        )

    def hybrid_search(
        self,
        query: str,
        *,
        tenant_id: str,
        product: str | None,
        version: str | None,
        limit: int,
    ) -> list[RetrievedCandidate]:
        conditions = [
            models.FieldCondition(
                key="metadata.tenant_id", match=models.MatchValue(value=tenant_id)
            )
        ]
        if product:
            conditions.append(
                models.FieldCondition(
                    key="metadata.product", match=models.MatchValue(value=product)
                )
            )
        if version:
            conditions.append(
                models.FieldCondition(
                    key="metadata.version", match=models.MatchValue(value=version)
                )
            )
        pairs = self.store.similarity_search_with_score(
            query=query,
            k=limit,
            filter=models.Filter(must=conditions),
            search_params=self._search_params(),
            hybrid_fusion=models.FusionQuery(fusion=models.Fusion.RRF),
        )
        return [
            RetrievedCandidate(document=document, hybrid_score=float(score))
            for document, score in pairs
        ]

    def ping(self) -> bool:
        self.client.get_collections()
        return True
