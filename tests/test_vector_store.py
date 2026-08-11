from langchain_core.documents import Document

from prodrag.config import Settings
from prodrag.vector_store import QdrantIndex


class RecordingClient:
    def __init__(self, events) -> None:
        self.events = events

    def set_payload(self, **kwargs) -> None:
        self.events.append(("ready", kwargs))

    def delete(self, **kwargs) -> None:
        self.events.append(("delete", kwargs))


class RecordingStore:
    def __init__(self, events) -> None:
        self.events = events

    def add_documents(self, **kwargs) -> None:
        self.events.append(("upload", kwargs))


class InspectableIndex(QdrantIndex):
    def __init__(self) -> None:
        self.settings = Settings(_env_file=None)
        self.events = []
        self.client = RecordingClient(self.events)
        self._recording_store = RecordingStore(self.events)

    @property
    def store(self):
        return self._recording_store


def test_revision_is_published_only_after_all_documents_upload() -> None:
    index = InspectableIndex()
    document = Document(
        page_content="content",
        metadata={
            "tenant_id": "acme",
            "document_id": "guide",
            "checksum": "new",
            "revision_ready": False,
        },
    )

    index.upsert_revision(
        [document],
        ["point-1"],
        document_id="guide",
        checksum="new",
        tenant_id="acme",
    )

    assert [event[0] for event in index.events] == ["upload", "ready", "delete"]
    assert index.events[1][1]["key"] == "metadata"
    assert index.events[1][1]["payload"] == {"revision_ready": True}
