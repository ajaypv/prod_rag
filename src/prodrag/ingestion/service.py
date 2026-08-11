from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from langchain_core.documents import Document

from prodrag.domain import ParsedDocument
from prodrag.ingestion.chunking import ChunkingStrategy
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner
from prodrag.models import IngestionResult
from prodrag.vector_store import QdrantIndex

_POINT_NAMESPACE = uuid.UUID("b8297a7c-3f58-4e30-bf8a-a33c8f3752bd")


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
    ) -> IngestionResult:
        checksum = file_checksum(source_path)
        parsed = self.parser.parse(source_path)
        sections = self.sectioner.split(parsed.markdown, default_heading=parsed.title)
        documents, point_ids = self._build_child_documents(
            parsed,
            sections,
            document_id=document_id,
            checksum=checksum,
            tenant_id=tenant_id,
            product=product,
            version=version,
        )
        self.index.upsert_revision(
            documents,
            point_ids,
            document_id=document_id,
            checksum=checksum,
            tenant_id=tenant_id,
        )
        return IngestionResult(
            document_id=document_id,
            checksum=checksum,
            parents_indexed=len(sections),
            chunks_indexed=len(documents),
        )

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
