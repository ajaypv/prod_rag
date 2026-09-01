"""Print the exact parent and child chunks prodRAG would create for Markdown.

This is a read-only learning and troubleshooting tool. It does not contact Qdrant,
SQLite, or Redis and it never indexes the source file. Semantic child inspection does
use the configured embedding model because production semantic boundaries depend on
those embeddings; pass ``--parents-only`` for a completely offline parent split.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from prodrag.clients import get_embeddings
from prodrag.config import get_settings
from prodrag.ingestion.chunking import SemanticChunkingStrategy
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner


def _estimated_tokens(text: str) -> int:
    """Mirror the conservative token counter used by the production chunker."""
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def _print_text(text: str, *, preview_chars: int) -> None:
    if preview_chars and len(text) > preview_chars:
        print(f"{text[:preview_chars].rstrip()}\n... [{len(text) - preview_chars} chars hidden]")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect the parent sections and semantic child chunks that prodRAG "
            "would create for a Markdown file. Nothing is indexed."
        )
    )
    parser.add_argument("path", help="Path to the Markdown file to inspect")
    parser.add_argument(
        "--parents-only",
        action="store_true",
        help="Print heading-based parents without calling the embedding model",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=0,
        metavar="N",
        help="Show at most N characters per chunk; 0 (default) prints full text",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = Path(args.path).resolve(strict=True)
    if source.suffix.lower() != ".md":
        raise SystemExit("This inspector expects a Markdown (.md) reference file")
    if args.preview_chars < 0:
        raise SystemExit("--preview-chars must be zero or greater")

    settings = get_settings()
    parsed = DoclingParser(max_file_bytes=settings.max_file_bytes).parse(source)
    parents = MarkdownSectioner(
        settings.parent_max_chars,
        settings.parent_max_tokens,
    ).split(
        parsed.markdown,
        default_heading=parsed.title,
    )

    chunker = None
    if not args.parents_only:
        chunker = SemanticChunkingStrategy(
            get_embeddings(),
            dimension=settings.oci_embed_dimension,
            chunk_size=settings.chunk_size_tokens,
            threshold=settings.semantic_threshold,
        )

    print("=" * 88)
    print("prodRAG CHUNK INSPECTION (READ ONLY)")
    print(f"Source             : {source}")
    print(f"Parent max chars   : {settings.parent_max_chars}")
    print(f"Parent max tokens  : {settings.parent_max_tokens}")
    print(f"Child target tokens: {settings.chunk_size_tokens}")
    print(f"Semantic threshold : {settings.semantic_threshold}")
    print(f"Parent count       : {len(parents)}")
    print("=" * 88)

    child_total = 0
    for parent_number, parent in enumerate(parents, start=1):
        print()
        print("#" * 88)
        print(f"PARENT {parent_number}/{len(parents)}")
        print(f"parent_id       : {parent.section_id}")
        print(f"heading         : {parent.heading}")
        print(f"section_order   : {parent.order}")
        print(f"part            : {parent.part}/{parent.part_count}")
        print(f"previous_parent : {parent.previous_parent_id or '-'}")
        print(f"next_parent     : {parent.next_parent_id or '-'}")
        print(f"characters      : {len(parent.text)}")
        print(f"estimated_tokens: {_estimated_tokens(parent.text)}")
        print("-" * 88)
        _print_text(parent.text, preview_chars=args.preview_chars)

        if chunker is None:
            continue

        children = chunker.chunk(parent.text)
        child_total += len(children)
        for child_number, child in enumerate(children, start=1):
            print()
            print(f"  CHILD {child_number}/{len(children)} -> parent_id={parent.section_id}")
            print(
                f"  characters={len(child)} | estimated_tokens={_estimated_tokens(child)}"
            )
            print("  " + "-" * 84)
            _print_text(child, preview_chars=args.preview_chars)

    print()
    print("=" * 88)
    if chunker is None:
        print(f"SUMMARY: {len(parents)} parents (child splitting skipped)")
    else:
        print(f"SUMMARY: {len(parents)} parents -> {child_total} semantic children")
    print("No data was written to SQLite, Qdrant, or Redis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
