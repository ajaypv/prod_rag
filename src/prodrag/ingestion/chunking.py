from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

import numpy as np
from chonkie import SemanticChunker
from chonkie.embeddings import BaseEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from prodrag.tokenization import conservative_token_count

_MARKDOWN_TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
_MARKDOWN_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_CODE_LANGUAGE_ALIASES = {
    "c++": "cpp",
    "cs": "csharp",
    "javascript": "js",
    "jsx": "js",
    "py": "python",
    "ps1": "powershell",
    "solidity": "sol",
    "typescript": "ts",
    "tsx": "ts",
}


class ChunkingStrategy(Protocol):
    def chunk(self, text: str) -> list[str]: ...


class OCIChonkieEmbeddings(BaseEmbeddings):
    """Adapt LangChain OCI embeddings to Chonkie's semantic chunker contract."""

    def __init__(self, embeddings: Embeddings, dimension: int) -> None:
        self._embeddings = embeddings
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> np.ndarray:
        return np.asarray(self._embeddings.embed_documents([text])[0], dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        return [
            np.asarray(vector, dtype=np.float32)
            for vector in self._embeddings.embed_documents(texts)
        ]

    def count_tokens(self, text: str) -> int:
        return conservative_token_count(text)

    def count_tokens_batch(self, texts: list[str]) -> list[int]:
        return [self.count_tokens(text) for text in texts]

    def get_tokenizer(self) -> Callable[[str], int]:
        return self.count_tokens

    @classmethod
    def is_available(cls) -> bool:
        return True

    def __repr__(self) -> str:
        return f"OCIChonkieEmbeddings(dimension={self.dimension})"


class SemanticChunkingStrategy:
    def __init__(
        self,
        embeddings: Embeddings,
        *,
        dimension: int,
        chunk_size: int = 450,
        threshold: float = 0.72,
    ) -> None:
        adapter = OCIChonkieEmbeddings(embeddings, dimension)
        self._count_tokens = adapter.count_tokens
        self._chunk_size = chunk_size
        self._size_guard = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
            keep_separator="end",
            chunk_size=chunk_size,
            chunk_overlap=0,
            length_function=adapter.count_tokens,
            strip_whitespace=True,
        )
        self._chunker = SemanticChunker(
            embedding_model=adapter,
            threshold=threshold,
            chunk_size=chunk_size,
            similarity_window=3,
            min_sentences_per_chunk=1,
            delim=[". ", "! ", "? ", "\n\n"],
            include_delim="prev",
        )

    def chunk(self, text: str) -> list[str]:
        table_spans = self._markdown_table_spans(text)
        code_spans = self._markdown_code_spans(text)
        if table_spans or code_spans:
            return self._chunk_structured_blocks(text, table_spans, code_spans)
        return self._chunk_prose(text)

    def _chunk_prose(self, text: str) -> list[str]:
        """Apply semantic splitting plus a strict size guard to unstructured prose."""
        chunks = self._chunker.chunk(text)
        semantic_chunks = [chunk.text.strip() for chunk in chunks if chunk.text.strip()]

        # Chonkie keeps semantic groups under chunk_size at sentence boundaries, but a
        # single delimiter-free sentence may itself be larger than the configured limit.
        # The stable LangChain recursive splitter is a deterministic final guard for that
        # pathological case while leaving normal semantic boundaries unchanged.
        output = [
            bounded
            for semantic_chunk in semantic_chunks or [text.strip()]
            for bounded in self._size_guard.split_text(semantic_chunk)
            if bounded
        ]
        return output or [text.strip()]

    def _chunk_structured_blocks(
        self,
        text: str,
        table_spans: list[tuple[int, int]],
        code_spans: list[tuple[int, int, str]],
    ) -> list[str]:
        """Keep tables and fenced code isolated from generic semantic splitting.

        A generic semantic splitter treats punctuation inside table cells as sentence
        boundaries. That can leave children beginning with an orphan pipe and without
        their column names. Table spans therefore bypass Chonkie. When a table is too
        large, each child repeats the header and separator so every row remains meaningful
        when embedded and retrieved independently. Code blocks likewise retain their
        fences and use language-aware or complete-line boundaries when they overflow.
        """
        lines = text.splitlines(keepends=True)
        output: list[str] = []
        cursor = 0
        blocks = sorted(
            [(start, end, "table", "") for start, end in table_spans]
            + [
                (start, end, "code", language)
                for start, end, language in code_spans
            ]
        )
        for start, end, block_type, language in blocks:
            prefix = "".join(lines[cursor:start]).strip()
            block = "".join(lines[start:end]).strip()

            # A heading or short introduction directly before a small structured block is
            # useful embedding context. Preserve the original parent as one child when it fits.
            combined = f"{prefix}\n\n{block}".strip() if prefix else block
            if prefix and self._count_tokens(combined) <= self._chunk_size:
                output.append(combined)
            else:
                if prefix:
                    output.extend(self._chunk_prose(prefix))
                if block_type == "table":
                    output.extend(self._chunk_table(block))
                else:
                    output.extend(self._chunk_code_block(block, language))
            cursor = end

        suffix = "".join(lines[cursor:]).strip()
        if suffix:
            output.extend(self._chunk_prose(suffix))
        return output

    def _chunk_code_block(self, block: str, language_name: str) -> list[str]:
        """Keep a fenced block whole or split its body at code-aware boundaries."""
        lines = block.splitlines()
        if len(lines) < 2 or not _MARKDOWN_FENCE.match(lines[0]):
            return self._size_guard.split_text(block)
        if self._count_tokens(block) <= self._chunk_size:
            return [block]

        opening_fence = lines[0].strip()
        opening_marker = _MARKDOWN_FENCE.match(lines[0])
        assert opening_marker is not None
        marker = opening_marker.group(1)
        has_closing_fence = bool(lines[-1].strip().startswith(marker[0] * len(marker)))
        closing_fence = lines[-1].strip() if has_closing_fence else marker
        body_lines = lines[1:-1] if has_closing_fence else lines[1:]
        body = "\n".join(body_lines).strip("\n")

        wrapper_tokens = self._count_tokens(f"{opening_fence}\n\n{closing_fence}")
        body_budget = self._chunk_size - wrapper_tokens
        if body_budget < 1:
            return self._size_guard.split_text(block)

        language = self._code_language(language_name)
        common_options = {
            "chunk_size": body_budget,
            "chunk_overlap": 0,
            "length_function": self._count_tokens,
            "keep_separator": "start",
            "strip_whitespace": False,
        }
        if language is not None:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=language,
                **common_options,
            )
        else:
            # Unknown languages still preserve blank-line and line boundaries. A single
            # line larger than the model budget is the only case that falls back to words
            # and characters, because the embedding limit must remain a hard constraint.
            splitter = RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", " ", ""],
                **common_options,
            )

        fragments = [fragment.strip("\n") for fragment in splitter.split_text(body)]
        return [
            f"{opening_fence}\n{fragment}\n{closing_fence}"
            for fragment in fragments
            if fragment
        ]

    @staticmethod
    def _code_language(language_name: str) -> Language | None:
        normalized = language_name.strip().lower().split(maxsplit=1)[0]
        normalized = _CODE_LANGUAGE_ALIASES.get(normalized, normalized)
        try:
            return Language(normalized)
        except ValueError:
            return None

    def _chunk_table(self, table: str) -> list[str]:
        lines = [line.strip() for line in table.splitlines() if line.strip()]
        if len(lines) < 2 or not self._is_table_separator(lines[1]):
            return self._size_guard.split_text(table)
        if self._count_tokens(table) <= self._chunk_size:
            return [table]

        header, separator, *rows = lines
        repeated_header = f"{header}\n{separator}"
        chunks: list[str] = []
        current_rows: list[str] = []

        for row in rows:
            candidate = "\n".join([repeated_header, *current_rows, row])
            if self._count_tokens(candidate) <= self._chunk_size:
                current_rows.append(row)
                continue

            if current_rows:
                chunks.append("\n".join([repeated_header, *current_rows]))
                current_rows = []

            single_row = f"{repeated_header}\n{row}"
            if self._count_tokens(single_row) <= self._chunk_size:
                current_rows.append(row)
            else:
                chunks.extend(self._chunk_oversized_table_row(header, row))

        if current_rows:
            chunks.append("\n".join([repeated_header, *current_rows]))
        return chunks or self._size_guard.split_text(table)

    def _chunk_oversized_table_row(self, header: str, row: str) -> list[str]:
        """Convert a single oversized row to labeled fields before strict splitting."""
        headings = self._markdown_cells(header)
        values = self._markdown_cells(row)
        if len(headings) == len(values) and headings:
            labeled_row = "\n".join(
                f"{name}: {value}" for name, value in zip(headings, values, strict=True)
            )
        else:
            labeled_row = row
        return self._size_guard.split_text(labeled_row)

    @staticmethod
    def _markdown_code_spans(text: str) -> list[tuple[int, int, str]]:
        """Return fenced-code line ranges and their declared language, if present."""
        lines = text.splitlines(keepends=True)
        spans: list[tuple[int, int, str]] = []
        index = 0
        while index < len(lines):
            opening = _MARKDOWN_FENCE.match(lines[index])
            if opening is None:
                index += 1
                continue

            marker = opening.group(1)
            language = lines[index][opening.end() :].strip()
            end = index + 1
            while end < len(lines):
                closing = _MARKDOWN_FENCE.match(lines[end])
                if (
                    closing is not None
                    and closing.group(1)[0] == marker[0]
                    and len(closing.group(1)) >= len(marker)
                ):
                    end += 1
                    break
                end += 1
            spans.append((index, end, language))
            index = end
        return spans

    @classmethod
    def _markdown_table_spans(cls, text: str) -> list[tuple[int, int]]:
        """Return line ranges for Markdown tables, excluding fenced code examples."""
        lines = text.splitlines(keepends=True)
        spans: list[tuple[int, int]] = []
        fence_character: str | None = None
        index = 0
        while index < len(lines):
            fence = _MARKDOWN_FENCE.match(lines[index])
            if fence:
                character = fence.group(1)[0]
                if fence_character is None:
                    fence_character = character
                elif fence_character == character:
                    fence_character = None
                index += 1
                continue

            if (
                fence_character is None
                and index + 1 < len(lines)
                and cls._is_table_row(lines[index])
                and cls._is_table_separator(lines[index + 1])
            ):
                end = index + 2
                while end < len(lines) and cls._is_table_row(lines[end]):
                    end += 1
                spans.append((index, end))
                index = end
                continue
            index += 1
        return spans

    @staticmethod
    def _markdown_cells(line: str) -> list[str]:
        stripped = line.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]

    @classmethod
    def _is_table_row(cls, line: str) -> bool:
        cells = cls._markdown_cells(line)
        return "|" in line and len(cells) >= 2 and any(cells)

    @classmethod
    def _is_table_separator(cls, line: str) -> bool:
        cells = cls._markdown_cells(line)
        return len(cells) >= 2 and all(
            _MARKDOWN_TABLE_SEPARATOR_CELL.fullmatch(cell.replace(" ", ""))
            for cell in cells
        )
