from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from langchain_core.documents import Document

from prodrag.domain import ParsedDocument
from prodrag.flow import FlowCallback, emit_flow_event
from prodrag.ingestion.chunking import ChunkingStrategy
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner
from prodrag.models import FlowStatus, IngestionResult
from prodrag.vector_store import QdrantIndex

_POINT_NAMESPACE = uuid.UUID("b8297a7c-3f58-4e30-bf8a-a33c8f3752bd")
_StageResult = TypeVar("_StageResult")


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IngestionService:
    def __init__(
        self,
        parser: DoclingParser,
        sectioner: MarkdownSectioner,
        chunker: ChunkingStrategy,
        index: QdrantIndex,
    ) -> None:
        self.parser = parser
        self.sectioner = sectioner
        self.chunker = chunker
        self.index = index

    def ingest(
        self,
        source_path: Path,
        *,
        document_id: str,
        tenant_id: str = "default",
        product: str | None = None,
        version: str | None = None,
        operation_id: str | None = None,
        on_stage: FlowCallback | None = None,
    ) -> IngestionResult:
        operation_id = operation_id or document_id
        checksum = self._run_stage(
            operation_id,
            "checksum",
            "Calculating a stable document checksum",
            "Document checksum calculated",
            lambda: file_checksum(source_path),
            on_stage,
            data=lambda value: {"checksum_prefix": value[:12]},
        )
        parsed = self._run_stage(
            operation_id,
            "parse",
            "Parsing source content with Docling",
            "Source content parsed",
            lambda: self.parser.parse(source_path),
            on_stage,
            data=lambda value: {
                "title": value.title,
                "extension": value.metadata.get("extension", ""),
            },
        )
        sections = self._run_stage(
            operation_id,
            "section",
            "Splitting parsed content into parent sections",
            "Parent sections created",
            lambda: self.sectioner.split(
                parsed.markdown,
                default_heading=parsed.title,
            ),
            on_stage,
            data=lambda value: {"parent_count": len(value)},
        )
        documents, point_ids = self._run_stage(
            operation_id,
            "chunk_embed",
            "Creating semantic child chunks and dense embeddings",
            "Semantic child chunks embedded",
            lambda: self._build_child_documents(
                parsed,
                sections,
                document_id=document_id,
                checksum=checksum,
                tenant_id=tenant_id,
                product=product,
                version=version,
            ),
            on_stage,
            data=lambda value: {"chunk_count": len(value[0])},
        )
        self._run_stage(
            operation_id,
            "index",
            "Writing the new revision to local Qdrant",
            "Local hybrid-search index updated",
            lambda: self.index.upsert_revision(
                documents,
                point_ids,
                document_id=document_id,
                checksum=checksum,
                tenant_id=tenant_id,
            ),
            on_stage,
            data=lambda _: {
                "parent_count": len(sections),
                "chunk_count": len(documents),
            },
        )
        return IngestionResult(
            document_id=document_id,
            checksum=checksum,
            parents_indexed=len(sections),
            chunks_indexed=len(documents),
        )

    @staticmethod
    def _run_stage(
        operation_id: str,
        stage: str,
        running_message: str,
        completed_message: str,
        operation: Callable[[], _StageResult],
        callback: FlowCallback | None,
        *,
        data: Callable[[_StageResult], dict[str, object]] | None = None,
    ) -> _StageResult:
        emit_flow_event(
            callback,
            operation_id=operation_id,
            stage=stage,
            status=FlowStatus.RUNNING,
            message=running_message,
        )
        started = time.perf_counter()
        try:
            result = operation()
        except Exception as exc:
            emit_flow_event(
                callback,
                operation_id=operation_id,
                stage=stage,
                status=FlowStatus.FAILED,
                message=f"{running_message} failed",
                duration_ms=(time.perf_counter() - started) * 1_000,
                data={"error_type": type(exc).__name__},
            )
            raise
        emit_flow_event(
            callback,
            operation_id=operation_id,
            stage=stage,
            status=FlowStatus.COMPLETED,
            message=completed_message,
            duration_ms=(time.perf_counter() - started) * 1_000,
            data=data(result) if data else None,
        )
        return result

    def _build_child_documents(
        self,
        parsed: ParsedDocument,
        sections,
        *,
        document_id: str,
        checksum: str,
        tenant_id: str,
        product: str | None,
        version: str | None,
    ) -> tuple[list[Document], list[str]]:
        documents: list[Document] = []
        point_ids: list[str] = []
        for section in sections:
            chunks = self.chunker.chunk(section.text)
            for child_order, child_text in enumerate(chunks):
                point_id = str(
                    uuid.uuid5(
                        _POINT_NAMESPACE,
                        f"{tenant_id}:{document_id}:{checksum}:{section.section_id}:{child_order}",
                    )
                )
                index_text = (
                    f"Document: {parsed.title}\n"
                    f"Section: {section.heading}\n\n"
                    f"{child_text.strip()}"
                )
                metadata = {
                    "document_id": document_id,
                    "checksum": checksum,
                    "tenant_id": tenant_id,
                    "title": parsed.title,
                    "source_name": parsed.metadata["source_name"],
                    "extension": parsed.metadata["extension"],
                    "section": section.heading,
                    "section_order": section.order,
                    "parent_id": section.section_id,
                    "parent_text": section.text,
                    "chunk_id": point_id,
                    "chunk_order": child_order,
                    # Qdrant search excludes this revision until every chunk is uploaded.
                    "revision_ready": False,
                }
                if product:
                    metadata["product"] = product
                if version:
                    metadata["version"] = version
                documents.append(Document(page_content=index_text, metadata=metadata))
                point_ids.append(point_id)
        if not documents:
            raise ValueError("No indexable chunks were produced")
        return documents, point_ids
