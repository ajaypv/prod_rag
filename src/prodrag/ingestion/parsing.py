from __future__ import annotations

import hashlib
import re
from pathlib import Path

from prodrag.config import SUPPORTED_EXTENSIONS
from prodrag.domain import ParentSection, ParsedDocument

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FIRST_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class UnsupportedDocumentError(ValueError):
    """The CLI received a file whose suffix is outside ``SUPPORTED_EXTENSIONS``."""
    pass


class EmptyDocumentError(ValueError):
    """Parsing or sectioning produced no searchable text."""
    pass


class DoclingParser:
    """Normalize a supported local file into Markdown without a parser service.

    Markdown and text take the direct UTF-8 path. PDF, DOCX, PPTX, and HTML lazily construct
    Docling because those formats need structural conversion. Docling may fetch model assets on
    the first PDF conversion, but document conversion itself runs on this machine.
    """

    def __init__(self, *, max_file_bytes: int, max_pages: int = 500) -> None:
        self.max_file_bytes = max_file_bytes
        self.max_pages = max_pages
        self._converter = None

    def parse(self, source_path: Path) -> ParsedDocument:
        """Validate, convert, clean, and title one document.

        Example: ``guide.pdf`` becomes one ``ParsedDocument`` whose ``markdown`` contains
        Docling's headings/tables. Those headings are the input to ``MarkdownSectioner.split``.
        A maximum page and byte limit prevents a CLI typo from starting an unbounded conversion.
        """
        source_path = source_path.resolve(strict=True)
        extension = source_path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedDocumentError(f"Unsupported document type: {extension}")
        if source_path.stat().st_size > self.max_file_bytes:
            raise ValueError(f"Document exceeds the {self.max_file_bytes}-byte ingestion limit")

        if extension in {".md", ".txt"}:
            markdown = source_path.read_text(encoding="utf-8", errors="replace")
        else:
            converter = self._get_converter()
            result = next(
                converter.convert_all(
                    [source_path],
                    raises_on_error=True,
                    max_num_pages=self.max_pages,
                    max_file_size=self.max_file_bytes,
                )
            )
            markdown = result.document.export_to_markdown()

        markdown = markdown.replace("\x00", "").strip()
        if not markdown:
            raise EmptyDocumentError(f"No indexable text was extracted from {source_path.name}")
        title_match = _FIRST_H1_RE.search(markdown)
        title = title_match.group(1).strip() if title_match else source_path.stem
        return ParsedDocument(
            source_path=source_path,
            title=title,
            markdown=markdown,
            metadata={"source_name": source_path.name, "extension": extension},
        )

    def _get_converter(self):
        """Create Docling only for the first rich document and reuse it for later files."""
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            # Docling keeps remote model services disabled by default. Do not enable them here.
            self._converter = DocumentConverter()
        return self._converter


class MarkdownSectioner:
    """Create answer-sized parent contexts along the document's heading hierarchy.

    Given ``# Auth`` followed by ``## Rotation``, the nested heading is stored as
    ``Auth > Rotation``. A 20,000-character section with a 12,000-character limit is split near
    paragraph boundaries, so every parent remains bounded before child chunking begins.
    """

    def __init__(self, max_parent_chars: int = 12_000) -> None:
        if max_parent_chars < 500:
            raise ValueError("max_parent_chars must be at least 500")
        self.max_parent_chars = max_parent_chars

    def split(self, markdown: str, *, default_heading: str = "Document") -> list[ParentSection]:
        """Split normalized Markdown into ordered parents with deterministic section IDs."""
        markdown = markdown.strip()
        if not markdown:
            raise EmptyDocumentError("Cannot section an empty document")

        raw_sections: list[tuple[str, str]] = []
        heading_stack: list[tuple[int, str]] = []
        current_heading = default_heading
        buffer: list[str] = []

        def flush() -> None:
            """Append the buffered body under the heading active immediately before it."""
            # Finish the previous heading body before moving into the next heading. Headings
            # themselves become metadata rather than being mixed into the preceding section.
            body = "\n".join(buffer).strip()
            if body:
                raw_sections.append((current_heading, body))

        for line in markdown.splitlines():
            match = _HEADING_RE.match(line)
            if not match:
                buffer.append(line)
                continue

            flush()
            buffer = []
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            heading_stack = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, heading_text))
            current_heading = " > ".join(item[1] for item in heading_stack)

        flush()
        if not raw_sections:
            raw_sections.append((default_heading, markdown))

        sections: list[ParentSection] = []
        for heading, body in raw_sections:
            for part in self._split_oversized(body):
                order = len(sections)
                section_text = f"{heading}\n\n{part}".strip()
                digest = hashlib.sha256(
                    f"{heading}\x00{order}\x00{section_text}".encode()
                ).hexdigest()[:24]
                sections.append(
                    ParentSection(
                        section_id=digest,
                        heading=heading,
                        text=section_text,
                        order=order,
                    )
                )
        return sections

    def _split_oversized(self, text: str) -> list[str]:
        """Prefer paragraph boundaries when a heading body exceeds the parent limit."""
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
        parts: list[str] = []
        current = ""

        def append_piece(piece: str) -> None:
            """Pack one paragraph into the current bounded parent or begin the next one."""
            # Accumulate paragraphs until adding one would cross the limit. This preserves
            # coherent prose better than slicing every parent at exactly max_parent_chars.
            nonlocal current
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if len(candidate) <= self.max_parent_chars:
                current = candidate
                return
            if current:
                parts.append(current)
                current = ""
            if len(piece) <= self.max_parent_chars:
                current = piece
                return
            parts.extend(self._hard_split(piece))

        for paragraph in paragraphs or [text]:
            append_piece(paragraph)
        if current:
            parts.append(current)
        return parts

    def _hard_split(self, text: str) -> list[str]:
        """Last-resort split for a single oversized paragraph, preferably at whitespace."""
        parts: list[str] = []
        remaining = text.strip()
        while len(remaining) > self.max_parent_chars:
            boundary = remaining.rfind(" ", 0, self.max_parent_chars + 1)
            if boundary < self.max_parent_chars // 2:
                boundary = self.max_parent_chars
            parts.append(remaining[:boundary].strip())
            remaining = remaining[boundary:].strip()
        if remaining:
            parts.append(remaining)
        return parts
