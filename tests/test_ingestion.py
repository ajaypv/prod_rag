from pathlib import Path

import pytest

from prodrag.ingestion import IngestionService
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner
from prodrag.models import FlowStatus


class FakeChunker:
    def chunk(self, text: str) -> list[str]:
        return [piece.strip() for piece in text.split("BREAK") if piece.strip()]


class FakeIndex:
    def __init__(self) -> None:
        self.calls = []

    def upsert_revision(self, documents, ids, **kwargs) -> None:
        self.calls.append((documents, ids, kwargs))


class FailingIndex(FakeIndex):
    def upsert_revision(self, documents, ids, **kwargs) -> None:
        super().upsert_revision(documents, ids, **kwargs)
        raise RuntimeError("Qdrant publish failed")


class FakeParentStore:
    def __init__(self) -> None:
        self.upserts = []
        self.prunes = []

    def upsert_revision(self, sections, **kwargs) -> None:
        self.upserts.append((sections, kwargs))

    def prune_revision(self, checksum, **kwargs) -> None:
        self.prunes.append((checksum, kwargs))


def test_ingestion_builds_deterministic_metadata_and_upserts(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Guide\n\nFirst. BREAK Second.", encoding="utf-8")
    index = FakeIndex()
    parent_store = FakeParentStore()
    events = []
    service = IngestionService(
        parser=DoclingParser(max_file_bytes=10_000),
        sectioner=MarkdownSectioner(max_parent_chars=2_000),
        chunker=FakeChunker(),
        parent_store=parent_store,  # type: ignore[arg-type]
        index=index,  # type: ignore[arg-type]
    )

    result = service.ingest(
        source,
        document_id="guide-v1",
        tenant_id="acme",
        product="router",
        version="1.0",
        operation_id="job-1",
        on_stage=events.append,
    )

    assert result.chunks_indexed == 2
    documents, point_ids, kwargs = index.calls[0]
    assert len(set(point_ids)) == 2
    assert kwargs["document_id"] == "guide-v1"
    assert all(document.metadata["tenant_id"] == "acme" for document in documents)
    assert all(document.metadata["parent_id"] for document in documents)
    assert all(document.metadata["parent_part"] == 1 for document in documents)
    assert all(document.metadata["parent_part_count"] == 1 for document in documents)
    assert all(document.metadata["parent_chunk_count"] == 2 for document in documents)
    assert all("parent_text" not in document.metadata for document in documents)
    assert parent_store.upserts[0][1]["checksum"] == result.checksum
    assert parent_store.prunes[0][0] == result.checksum
    assert [(event.stage, event.status) for event in events] == [
        ("checksum", FlowStatus.RUNNING),
        ("checksum", FlowStatus.COMPLETED),
        ("parse", FlowStatus.RUNNING),
        ("parse", FlowStatus.COMPLETED),
        ("section", FlowStatus.RUNNING),
        ("section", FlowStatus.COMPLETED),
        ("parent_store", FlowStatus.RUNNING),
        ("parent_store", FlowStatus.COMPLETED),
        ("chunk_embed", FlowStatus.RUNNING),
        ("chunk_embed", FlowStatus.COMPLETED),
        ("index", FlowStatus.RUNNING),
        ("index", FlowStatus.COMPLETED),
    ]
    assert all(event.operation_id == "job-1" for event in events)

    second_index = FakeIndex()
    second_parent_store = FakeParentStore()
    second_service = IngestionService(
        parser=DoclingParser(max_file_bytes=10_000),
        sectioner=MarkdownSectioner(max_parent_chars=2_000),
        chunker=FakeChunker(),
        parent_store=second_parent_store,  # type: ignore[arg-type]
        index=second_index,  # type: ignore[arg-type]
    )
    second_service.ingest(source, document_id="guide-v1", tenant_id="acme")
    assert second_index.calls[0][1] == point_ids


def test_failed_qdrant_publish_does_not_prune_previous_parents(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Guide\n\nKeep the previous revision safe.", encoding="utf-8")
    parent_store = FakeParentStore()
    service = IngestionService(
        parser=DoclingParser(max_file_bytes=10_000),
        sectioner=MarkdownSectioner(max_parent_chars=2_000),
        chunker=FakeChunker(),
        parent_store=parent_store,  # type: ignore[arg-type]
        index=FailingIndex(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="Qdrant publish failed"):
        service.ingest(source, document_id="guide-v2", tenant_id="acme")

    # New parents may exist as harmless orphans, but parents used by the previous
    # searchable Qdrant revision are not removed until publication succeeds.
    assert len(parent_store.upserts) == 1
    assert parent_store.prunes == []
