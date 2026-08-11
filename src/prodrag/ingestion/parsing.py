from __future__ import annotations

import hashlib
import re
from pathlib import Path

from prodrag.config import SUPPORTED_EXTENSIONS
from prodrag.domain import ParentSection, ParsedDocument

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FIRST_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class UnsupportedDocumentError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


class DoclingParser:
    """Parse local technical documents without sending their contents to a parser service."""

    def __init__(
        self,
        *,
        max_file_bytes: int,
        max_pages: int = 500,
        pdf_ocr_enabled: bool = False,
        pdf_table_structure_enabled: bool = False,
        pdf_force_backend_text: bool = True,
    ) -> None:
        self.max_file_bytes = max_file_bytes
        self.max_pages = max_pages
        self.pdf_ocr_enabled = pdf_ocr_enabled
        self.pdf_table_structure_enabled = pdf_table_structure_enabled
        self.pdf_force_backend_text = pdf_force_backend_text
        self._converter = None

    def parse(self, source_path: Path) -> ParsedDocument:
        source_path = source_path.resolve(strict=True)
        extension = source_path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedDocumentError(f"Unsupported document type: {extension}")
        if source_path.stat().st_size > self.max_file_bytes:
            raise ValueError(f"Document exceeds the {self.max_file_bytes}-byte ingestion limit")

        if extension in {".md", ".txt"}:
            markdown = source_path.read_text(encoding="utf-8", errors="replace")
        elif extension == ".pdf" and self._use_native_pdf_extraction():
            markdown = self._extract_native_pdf_text(source_path)
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

    def _use_native_pdf_extraction(self) -> bool:
        return (
            self.pdf_force_backend_text
            and not self.pdf_ocr_enabled
            and not self.pdf_table_structure_enabled
        )

    def _extract_native_pdf_text(self, source_path: Path) -> str:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(source_path)
        try:
            page_count = len(document)
            if page_count > self.max_pages:
                raise ValueError(
                    f"Document exceeds the {self.max_pages}-page ingestion limit"
                )
            pages: list[str] = []
            for page_number in range(page_count):
                page = document[page_number]
                try:
                    text_page = page.get_textpage()
                    try:
                        text = text_page.get_text_range().strip()
                    finally:
                        text_page.close()
                finally:
                    page.close()
                if text:
                    pages.append(f"## Page {page_number + 1}\n\n{text}")
            return "\n\n".join(pages)
        finally:
            document.close()

    def _get_converter(self):
        if self._converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            # Docling keeps remote model services disabled by default. Do not enable them here.
            pdf_options = PdfPipelineOptions(
                do_ocr=self.pdf_ocr_enabled,
                do_table_structure=self.pdf_table_structure_enabled,
                force_backend_text=self.pdf_force_backend_text,
            )
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
                }
            )
        return self._converter


class MarkdownSectioner:
    """Create parent sections along Markdown headings before semantic child chunking."""

    def __init__(self, max_parent_chars: int = 12_000) -> None:
        if max_parent_chars < 500:
            raise ValueError("max_parent_chars must be at least 500")
        self.max_parent_chars = max_parent_chars

    def split(self, markdown: str, *, default_heading: str = "Document") -> list[ParentSection]:
        markdown = markdown.strip()
        if not markdown:
            raise EmptyDocumentError("Cannot section an empty document")

        raw_sections: list[tuple[str, str]] = []
        heading_stack: list[tuple[int, str]] = []
        current_heading = default_heading
        buffer: list[str] = []

        def flush() -> None:
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
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
        parts: list[str] = []
        current = ""

        def append_piece(piece: str) -> None:
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
