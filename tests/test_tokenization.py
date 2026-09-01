from prodrag.tokenization import markdown_atomic_blocks, take_markdown_prefix


def test_markdown_atomic_blocks_keep_loose_list_together() -> None:
    text = """Before.

- first item

- second item

  continuation paragraph

After.
"""

    blocks = markdown_atomic_blocks(text)

    assert blocks == [
        "Before.",
        "- first item\n\n- second item\n\n  continuation paragraph",
        "After.",
    ]


def test_markdown_atomic_blocks_use_matching_fence_length() -> None:
    text = """````python
print("start")

```python
not_the_closing_fence = True
```
````

After.
"""

    blocks = markdown_atomic_blocks(text)

    assert len(blocks) == 2
    assert "not_the_closing_fence = True" in blocks[0]
    assert blocks[1] == "After."


def test_markdown_prefix_ends_on_complete_block() -> None:
    text = "first paragraph\n\nsecond paragraph is too large"

    prefix = take_markdown_prefix(text, max_tokens=2, max_chars=100)

    assert prefix == "first paragraph"
