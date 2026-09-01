from __future__ import annotations

import re
from collections.abc import Callable

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])[ \t]+")

TokenCounter = Callable[[str], int]


def conservative_token_count(text: str) -> int:
    """Count words and punctuation as a deterministic upper-leaning token estimate.

    OCI Embed 4 documents token limits but does not expose its tokenizer through the
    inference API. The same conservative counter is therefore used for parent, child,
    neighbor, and answer budgets so those layers cannot silently disagree.
    """
    return len(_TOKEN_RE.findall(text))


def fits_text_budget(
    text: str,
    *,
    max_tokens: int,
    max_chars: int,
    token_counter: TokenCounter = conservative_token_count,
) -> bool:
    return len(text) <= max_chars and token_counter(text) <= max_tokens


def markdown_atomic_blocks(text: str) -> list[str]:
    """Split at blank lines outside fences while keeping structured blocks intact.

    Markdown tables, lists, and ordinary paragraphs contain no internal blank line in
    their common form and remain one block. Fenced code is tracked explicitly so blank
    lines inside a function do not divide the block.
    """
    blocks: list[str] = []
    current: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    lines = text.strip("\r\n").splitlines()

    def flush() -> None:
        block = "\n".join(current).strip("\r\n")
        if block.strip():
            blocks.append(block)
        current.clear()

    def current_is_list() -> bool:
        return any(_LIST_ITEM_RE.match(line) for line in current if line.strip())

    def list_continues(after: int) -> bool:
        for following in lines[after:]:
            if not following.strip():
                continue
            return bool(
                _LIST_ITEM_RE.match(following)
                or following.startswith((" ", "\t"))
            )
        return False

    for index, line in enumerate(lines):
        fence = _FENCE_RE.match(line)
        if fence_character is not None:
            current.append(line)
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
            current.append(line)
            continue

        if not line.strip() and fence_character is None:
            # A loose Markdown list may contain blank lines between items or before
            # an indented continuation paragraph. Keep those lines in the same
            # structural block instead of turning each item into unrelated evidence.
            if current_is_list() and list_continues(index + 1):
                current.append(line)
                continue
            flush()
            continue
        current.append(line)

    flush()
    return [block for block in blocks if block]


def take_markdown_prefix(
    text: str,
    *,
    max_tokens: int,
    max_chars: int,
    token_counter: TokenCounter = conservative_token_count,
) -> str:
    """Return the largest prefix ending at an atomic Markdown block boundary."""
    accepted: list[str] = []
    for block in markdown_atomic_blocks(text):
        candidate = "\n\n".join([*accepted, block])
        if not fits_text_budget(
            candidate,
            max_tokens=max_tokens,
            max_chars=max_chars,
            token_counter=token_counter,
        ):
            break
        accepted.append(block)
    return "\n\n".join(accepted)
