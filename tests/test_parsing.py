from pathlib import Path

import pytest

from prodrag.ingestion.parsing import DoclingParser, EmptyDocumentError, MarkdownSectioner
from prodrag.tokenization import conservative_token_count


def test_pdf_parser_defaults_to_native_text_without_ocr() -> None:
    parser = DoclingParser(max_file_bytes=10_000)

    assert parser.pdf_ocr_enabled is False
    assert parser.pdf_table_structure_enabled is False
    assert parser.pdf_force_backend_text is True
    assert parser._use_native_pdf_extraction() is True


def test_pdf_parser_uses_docling_when_ocr_is_enabled() -> None:
    parser = DoclingParser(max_file_bytes=10_000, pdf_ocr_enabled=True)

    assert parser._use_native_pdf_extraction() is False


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


def test_markdown_sectioner_preserves_hash_in_heading_text() -> None:
    sections = MarkdownSectioner(max_parent_chars=2_000).split(
        "# C# integration\n\nUse the supported SDK."
    )

    assert sections[0].heading == "C# integration"


def test_markdown_sectioner_does_not_treat_fenced_code_as_document_headings() -> None:
    markdown = """# Operations

Use this example:

```markdown
# This is code, not a document heading
example=true
```

## Recovery

Restart the service.
"""

    sections = MarkdownSectioner(max_parent_chars=2_000).split(markdown)

    assert [section.heading for section in sections] == [
        "Operations",
        "Operations > Recovery",
    ]
    assert "# This is code, not a document heading" in sections[0].text


def test_markdown_sectioner_hard_caps_parent_size() -> None:
    sections = MarkdownSectioner(max_parent_chars=500).split("word " * 400)

    assert len(sections) > 1
    assert all(len(section.text) <= 500 for section in sections)


def test_markdown_sectioner_uses_token_budget_and_links_parts() -> None:
    paragraphs = [
        " ".join([f"paragraph-{index}", *(f"token{item}" for item in range(55))])
        for index in range(4)
    ]
    sections = MarkdownSectioner(
        max_parent_chars=10_000,
        max_parent_tokens=100,
    ).split(f"# Guide\n\n{'\n\n'.join(paragraphs)}")

    assert len(sections) == 4
    assert [section.part for section in sections] == [1, 2, 3, 4]
    assert all(section.part_count == 4 for section in sections)
    assert sections[0].previous_parent_id is None
    assert sections[0].next_parent_id == sections[1].section_id
    assert sections[1].previous_parent_id == sections[0].section_id
    assert sections[-1].next_parent_id is None
    assert all(section.text.startswith("Guide\n\n") for section in sections)
    assert all(conservative_token_count(section.text) <= 100 for section in sections)


def test_markdown_sectioner_keeps_code_and_table_blocks_atomic_when_they_fit() -> None:
    markdown = """# Examples

```python
def first():
    return 1

def second():
    return 2
```

| Name | Value |
|---|---|
| alpha | one |
| beta | two |
"""
    sections = MarkdownSectioner(
        max_parent_chars=2_000,
        max_parent_tokens=100,
    ).split(markdown)

    combined = "\n\n".join(section.text for section in sections)
    assert "```python\ndef first():\n    return 1\n\ndef second():\n    return 2\n```" in combined
    assert "| Name | Value |\n|---|---|\n| alpha | one |\n| beta | two |" in combined


def test_markdown_sectioner_rejects_empty_input() -> None:
    with pytest.raises(EmptyDocumentError):
        MarkdownSectioner().split("   ")


def test_parser_reads_markdown_without_docling(tmp_path: Path) -> None:
    source = tmp_path / "faq.md"
    source.write_text("# FAQ\n\n## Reset\n\nPress reset.", encoding="utf-8")

    parsed = DoclingParser(max_file_bytes=10_000).parse(source)

    assert parsed.title == "FAQ"
    assert parsed.metadata["source_name"] == "faq.md"
