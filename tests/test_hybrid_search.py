from langchain_core.documents import Document
from qdrant_client import models

from prodrag.config import Settings
from prodrag.vector_store import QdrantIndex


class RecordingStore:
    def __init__(self) -> None:
        self.arguments = {}

    def similarity_search_with_score(self, **kwargs):
        self.arguments = kwargs
        return [(Document(page_content="matched context"), 0.75)]


class InspectableQdrantIndex(QdrantIndex):
    def __init__(self, settings: Settings, store: RecordingStore) -> None:
        self.settings = settings
        self.recording_store = store

    @property
    def store(self):
        return self.recording_store


def test_blank_qdrant_path_selects_server_mode() -> None:
    settings = Settings(_env_file=None, qdrant_path="", qdrant_hnsw_enabled=True)

    assert settings.qdrant_path is None


def test_qdrant_hybrid_search_explicitly_uses_rrf_fusion() -> None:
    store = RecordingStore()
    index = InspectableQdrantIndex(Settings(_env_file=None), store)

    results = index.hybrid_search(
        "HTTP 429",
        tenant_id="demo",
        product="nimbusflow",
        version="1.0",
        limit=20,
    )

    assert results[0].hybrid_score == 0.75
    assert store.arguments["hybrid_fusion"].fusion == models.Fusion.RRF
    assert store.arguments["search_params"].exact is True
    readiness = store.arguments["filter"].must[1]
    assert isinstance(readiness, models.Filter)
    assert readiness.should[0].key == "metadata.revision_ready"


def test_qdrant_embedded_mode_omits_unsupported_search_params() -> None:
    store = RecordingStore()
    settings = Settings(_env_file=None, qdrant_path="./data/qdrant")
    index = InspectableQdrantIndex(settings, store)

    index.hybrid_search(
        "HTTP 429",
        tenant_id="demo",
        product="nimbusflow",
        version="1.0",
        limit=20,
    )

    assert store.arguments["search_params"] is None

def test_qdrant_hybrid_search_can_enable_hnsw() -> None:
    store = RecordingStore()
    settings = Settings(
        _env_file=None,
        qdrant_hnsw_enabled=True,
        qdrant_hnsw_ef_search=192,
    )
    index = InspectableQdrantIndex(settings, store)

    index.hybrid_search(
        "HTTP 429",
        tenant_id="demo",
        product="nimbusflow",
        version="1.0",
        limit=20,
    )

    assert store.arguments["search_params"].exact is False
    assert store.arguments["search_params"].hnsw_ef == 192
