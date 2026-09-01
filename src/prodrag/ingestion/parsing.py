from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path

from prodrag.config import SUPPORTED_EXTENSIONS
from prodrag.domain import ParentSection, ParsedDocument
from prodrag.tokenization import (
    conservative_token_count,
    fits_text_budget,
    markdown_atomic_blocks,
)

_FIRST_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_MARKDOWN_HEADING = re.compile(
    r"^(?P<marks>#{1,6})[ \t]+(?P<title>.*?)(?:[ \t]+#+[ \t]*)?(?:\r?\n)?$"
)
_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


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
    """Create bounded, linked parent parts along the Markdown heading hierarchy."""

    def __init__(
        self,
        max_parent_chars: int = 8_000,
        max_parent_tokens: int = 2_000,
        token_counter: Callable[[str], int] = conservative_token_count,
    ) -> None:
        if max_parent_chars < 500:
            raise ValueError("max_parent_chars must be at least 500")
        if max_parent_tokens < 100:
            raise ValueError("max_parent_tokens must be at least 100")
        self.max_parent_chars = max_parent_chars
        self.max_parent_tokens = max_parent_tokens
        self._count_tokens = token_counter

    def split(self, markdown: str, *, default_heading: str = "Document") -> list[ParentSection]:
        markdown = markdown.strip()
        if not markdown:
            raise EmptyDocumentError("Cannot section an empty document")

        raw_sections = self._split_heading_sections(markdown, default_heading)

        if not raw_sections:
            raw_sections.append((default_heading, markdown))

        drafts: list[tuple[str, str, int, int]] = []
        groups: list[range] = []
        for heading, body in raw_sections:
            parts = self._split_oversized(heading, body)
            group_start = len(drafts)
            for part_number, part in enumerate(parts, start=1):
                section_text = f"{heading}\n\n{part}".strip()
                drafts.append((heading, section_text, part_number, len(parts)))
            groups.append(range(group_start, len(drafts)))

        section_ids = [
            hashlib.sha256(
                f"{heading}\x00{order}\x00{text}".encode()
            ).hexdigest()[:24]
            for order, (heading, text, _, _) in enumerate(drafts)
        ]
        neighbors: dict[int, tuple[str | None, str | None]] = {}
        for group in groups:
            indexes = list(group)
            for position, index in enumerate(indexes):
                previous_id = section_ids[indexes[position - 1]] if position > 0 else None
                next_id = (
                    section_ids[indexes[position + 1]]
                    if position + 1 < len(indexes)
                    else None
                )
                neighbors[index] = (previous_id, next_id)

        sections = []
        for order, (heading, text, part, part_count) in enumerate(drafts):
            previous_id, next_id = neighbors[order]
            sections.append(
                ParentSection(
                    section_id=section_ids[order],
                    heading=heading,
                    text=text,
                    order=order,
                    part=part,
                    part_count=part_count,
                    previous_parent_id=previous_id,
                    next_parent_id=next_id,
                )
            )
        return sections

    @staticmethod
    def _split_heading_sections(
        markdown: str, default_heading: str
    ) -> list[tuple[str, str]]:
        """Split on real H1-H6 headings without modifying body whitespace.

        LangChain's stable ``MarkdownHeaderTextSplitter`` normalizes individual
        lines while collecting them. That behavior is useful for prose but removes
        leading indentation from Python and other whitespace-sensitive fenced code.
        This small scanner owns only the heading boundary: downstream size splitting
        still works on Markdown blocks and keeps their original text intact.

        A heading seen inside a backtick or tilde fence is ordinary code. Outside a
        fence, the current H1-H6 stack is updated and the complete hierarchy becomes
        the label repeated on every bounded parent part.
        """
        sections: list[tuple[str, str]] = []
        hierarchy: list[str | None] = [None] * 6
        current_heading = default_heading
        current_lines: list[str] = []
        fence_character: str | None = None
        fence_length = 0

        def flush() -> None:
            body = "".join(current_lines).strip("\r\n")
            if body.strip():
                sections.append((current_heading, body))
            current_lines.clear()

        for line in markdown.splitlines(keepends=True):
            fence = _FENCE.match(line)
            if fence_character is not None:
                current_lines.append(line)
                if (
                    fence
                    and fence.group(1)[0] == fence_character
                    and len(fence.group(1)) >= fence_length
                    and not line[fence.end() :].strip()
                ):
                    fence_character = None
                    fence_length = 0
                continue

            if fence:
                fence_character = fence.group(1)[0]
                fence_length = len(fence.group(1))
                current_lines.append(line)
                continue

            heading_match = _MARKDOWN_HEADING.match(line)
            if not heading_match:
                current_lines.append(line)
                continue

            flush()
            level = len(heading_match.group("marks"))
            title = heading_match.group("title").strip()
            hierarchy[level - 1] = title
            hierarchy[level:] = [None] * (6 - level)
            current_heading = " > ".join(
                item for item in hierarchy[:level] if item
            ) or default_heading

        flush()
        return sections

    def _split_oversized(self, heading: str, text: str) -> list[str]:
        blocks = markdown_atomic_blocks(text)
        parts: list[str] = []
        current = ""

        for block in blocks or [text.strip()]:
            candidate = f"{current}\n\n{block}".strip() if current else block
            if self._fits(heading, candidate):
                current = candidate
                continue
            if current:
                parts.append(current)
                current = ""
            if self._fits(heading, block):
                current = block
            else:
                parts.extend(self._split_atomic_block(heading, block))
        if current:
            parts.append(current)
        return parts

    def _fits(self, heading: str, body: str) -> bool:
        return fits_text_budget(
            f"{heading}\n\n{body}".strip(),
            max_tokens=self.max_parent_tokens,
            max_chars=self.max_parent_chars,
            token_counter=self._count_tokens,
        )

    def _split_atomic_block(self, heading: str, block: str) -> list[str]:
        lines = block.splitlines()
        if lines and _FENCE.match(lines[0]):
            return self._split_fenced_block(heading, lines)
        if len(lines) >= 2 and self._is_table_separator(lines[1]):
            return self._split_table(heading, lines)
        return self._pack_lines(heading, lines)

    def _split_fenced_block(self, heading: str, lines: list[str]) -> list[str]:
        opening = lines[0].strip()
        marker_match = _FENCE.match(opening)
        assert marker_match is not None
        marker = marker_match.group(1)
        has_closing = len(lines) > 1 and lines[-1].strip().startswith(
            marker[0] * len(marker)
        )
        closing = lines[-1].strip() if has_closing else marker
        body_lines = lines[1:-1] if has_closing else lines[1:]
        return self._pack_lines(
            heading,
            body_lines,
            prefix=opening,
            suffix=closing,
        )

    def _split_table(self, heading: str, lines: list[str]) -> list[str]:
        header = lines[0].strip()
        separator = lines[1].strip()
        prefix = f"{header}\n{separator}"
        rows = [line.strip() for line in lines[2:] if line.strip()]
        return self._pack_lines(heading, rows, prefix=prefix)

    def _pack_lines(
        self,
        heading: str,
        lines: list[str],
        *,
        prefix: str = "",
        suffix: str = "",
    ) -> list[str]:
        parts: list[str] = []
        current: list[str] = []

        def render(body_lines: list[str]) -> str:
            items = ([prefix] if prefix else []) + body_lines + ([suffix] if suffix else [])
            return "\n".join(items).strip()

        for line in lines:
            candidate = render([*current, line])
            if self._fits(heading, candidate):
                current.append(line)
                continue
            if current:
                parts.append(render(current))
                current = []
            single = render([line])
            if self._fits(heading, single):
                current.append(line)
            else:
                parts.extend(
                    self._split_words(
                        heading,
                        line,
                        prefix=prefix,
                        suffix=suffix,
                    )
                )
        if current or not parts:
            rendered = render(current)
            if rendered:
                parts.append(rendered)
        return parts

    def _split_words(
        self,
        heading: str,
        text: str,
        *,
        prefix: str = "",
        suffix: str = "",
    ) -> list[str]:
        words = text.split()
        parts: list[str] = []
        current: list[str] = []

        def render(items: list[str]) -> str:
            body = " ".join(items)
            return "\n".join(item for item in (prefix, body, suffix) if item).strip()

        for word in words:
            if self._fits(heading, render([*current, word])):
                current.append(word)
                continue
            if current:
                parts.append(render(current))
                current = []
            if self._fits(heading, render([word])):
                current.append(word)
            else:
                parts.extend(self._split_long_word(heading, word, prefix, suffix))
        if current:
            parts.append(render(current))
        return parts

    def _split_long_word(
        self, heading: str, word: str, prefix: str, suffix: str
    ) -> list[str]:
        parts: list[str] = []
        remaining = word
        while remaining:
            low, high = 1, len(remaining)
            accepted = 0
            while low <= high:
                middle = (low + high) // 2
                candidate = "\n".join(
                    item for item in (prefix, remaining[:middle], suffix) if item
                )
                if self._fits(heading, candidate):
                    accepted = middle
                    low = middle + 1
                else:
                    high = middle - 1
            if accepted == 0:
                raise ValueError("Parent heading and structural prefix exceed the parent budget")
            piece = "\n".join(
                item for item in (prefix, remaining[:accepted], suffix) if item
            )
            parts.append(piece)
            remaining = remaining[accepted:]
        return parts

    @staticmethod
    def _markdown_cells(line: str) -> list[str]:
        stripped = line.strip().strip("|")
        return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]

    @classmethod
    def _is_table_separator(cls, line: str) -> bool:
        cells = cls._markdown_cells(line)
        return len(cells) >= 2 and all(
            _TABLE_SEPARATOR_CELL.fullmatch(cell.replace(" ", "")) for cell in cells
        )
