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

# A fixed namespace makes every child point ID reproducible for the same document revision.
_POINT_NAMESPACE = uuid.UUID("b8297a7c-3f58-4e30-bf8a-a33c8f3752bd")


def file_checksum(path: Path) -> str:
    """Stream a SHA-256 checksum without loading a potentially large document into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IngestionService:
    """Run the synchronous file-to-Qdrant pipeline used by ``prodrag ingest``.

    The service intentionally finishes a complete new checksum revision before asking Qdrant to
    remove stale points. If embedding chunk 19 fails, the previous good revision remains fully
    searchable instead of being deleted first.
    """
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
        """Parse one file, create searchable children, and atomically replace its revision.

        Each Qdrant point stores a focused child as ``page_content`` and its full parent in
        metadata. For example, search may match a 450-token "rotation steps" child, while answer
        generation later expands it to the complete "API token rotation" parent.
        """
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
        """Convert parent sections into Qdrant children and matching deterministic IDs.

        The child text is the dense/sparse search unit. Its metadata carries the complete parent,
        filters, checksum, and citation fields used later by retrieval and answering.
        """
        documents: list[Document] = []
        point_ids: list[str] = []
        for section in sections:
            chunks = self.chunker.chunk(section.text)
            for child_order, child_text in enumerate(chunks):
                # Including the checksum creates new point IDs when document content changes,
                # while repeated ingestion of an unchanged revision remains idempotent.
                point_id = str(
                    uuid.uuid5(
                        _POINT_NAMESPACE,
                        f"{tenant_id}:{document_id}:{checksum}:{section.section_id}:{child_order}",
                    )
                )
                # UUID5 makes identical inputs produce identical point IDs. Retrying the same
                # revision therefore updates the same logical points rather than duplicating them.
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
                    # Parent text is stored with each child so retrieval can expand a precise
                    # child match back to a coherent section without another document lookup.
                    "parent_text": section.text,
                    "chunk_id": point_id,
                    "chunk_order": child_order,
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
