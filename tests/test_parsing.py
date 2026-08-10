from pathlib import Path

import pytest

from prodrag.ingestion.parsing import DoclingParser, EmptyDocumentError, MarkdownSectioner


def test_markdown_sectioner_preserves_heading_hierarchy_and_content() -> None:
    markdown = """# Product Guide

Overview text.

## Authentication

Use an API token.

### Rotation

Rotate it every 90 days.
"""

    sections = MarkdownSectioner(max_parent_chars=2_000).split(markdown)

    assert [section.heading for section in sections] == [
        "Product Guide",
        "Product Guide > Authentication",
        "Product Guide > Authentication > Rotation",
    ]
    combined = "\n".join(section.text for section in sections)
    assert "Overview text." in combined
    assert "Use an API token." in combined
    assert "Rotate it every 90 days." in combined


def test_markdown_sectioner_hard_caps_parent_size() -> None:
    sections = MarkdownSectioner(max_parent_chars=500).split("word " * 400)

    assert len(sections) > 1
    # The heading is added after body splitting, so allow its small prefix.
    assert all(len(section.text) <= 520 for section in sections)


def test_markdown_sectioner_rejects_empty_input() -> None:
    with pytest.raises(EmptyDocumentError):
        MarkdownSectioner().split("   ")


def test_parser_reads_markdown_without_docling(tmp_path: Path) -> None:
    source = tmp_path / "faq.md"
    source.write_text("# FAQ\n\n## Reset\n\nPress reset.", encoding="utf-8")

    parsed = DoclingParser(max_file_bytes=10_000).parse(source)

    assert parsed.title == "FAQ"
    assert parsed.metadata["source_name"] == "faq.md"

