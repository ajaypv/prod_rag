from pathlib import Path

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


def test_ingestion_builds_deterministic_metadata_and_upserts(tmp_path: Path) -> None:
    source = tmp_path / "guide.md"
    source.write_text("# Guide\n\nFirst. BREAK Second.", encoding="utf-8")
    index = FakeIndex()
    events = []
    service = IngestionService(
        parser=DoclingParser(max_file_bytes=10_000),
        sectioner=MarkdownSectioner(max_parent_chars=2_000),
        chunker=FakeChunker(),
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
    assert all(document.metadata["parent_text"] for document in documents)
    assert [(event.stage, event.status) for event in events] == [
        ("checksum", FlowStatus.RUNNING),
        ("checksum", FlowStatus.COMPLETED),
        ("parse", FlowStatus.RUNNING),
        ("parse", FlowStatus.COMPLETED),
        ("section", FlowStatus.RUNNING),
        ("section", FlowStatus.COMPLETED),
        ("chunk_embed", FlowStatus.RUNNING),
        ("chunk_embed", FlowStatus.COMPLETED),
        ("index", FlowStatus.RUNNING),
        ("index", FlowStatus.COMPLETED),
    ]
    assert all(event.operation_id == "job-1" for event in events)

    second_index = FakeIndex()
    second_service = IngestionService(
        parser=DoclingParser(max_file_bytes=10_000),
        sectioner=MarkdownSectioner(max_parent_chars=2_000),
        chunker=FakeChunker(),
        index=second_index,  # type: ignore[arg-type]
    )
    second_service.ingest(source, document_id="guide-v1", tenant_id="acme")
    assert second_index.calls[0][1] == point_ids
