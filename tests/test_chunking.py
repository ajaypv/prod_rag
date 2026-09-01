from langchain_core.embeddings import Embeddings

from prodrag.ingestion.chunking import OCIChonkieEmbeddings, SemanticChunkingStrategy


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_recursive_size_guard_splits_one_oversized_sentence() -> None:
    embeddings = FakeEmbeddings()
    strategy = SemanticChunkingStrategy(
        embeddings,
        dimension=3,
        chunk_size=20,
        threshold=0.72,
    )

    chunks = strategy.chunk(" ".join(f"token{index}" for index in range(55)))
    counter = OCIChonkieEmbeddings(embeddings, dimension=3)

    assert len(chunks) == 3
    assert all(counter.count_tokens(chunk) <= 20 for chunk in chunks)
    assert " ".join(chunks).split() == [f"token{index}" for index in range(55)]


def test_small_markdown_table_stays_whole() -> None:
    strategy = SemanticChunkingStrategy(
        FakeEmbeddings(),
        dimension=3,
        chunk_size=100,
        threshold=0.72,
    )
    text = """Support matrix

| Area | Source | Question |
|---|---|---|
| Billing | billing.md | Where is my invoice? |
| API | limits.md | What should I do after HTTP 429? |"""

    assert strategy.chunk(text) == [text]


def test_large_markdown_table_splits_rows_and_repeats_headers() -> None:
    embeddings = FakeEmbeddings()
    strategy = SemanticChunkingStrategy(
        embeddings,
        dimension=3,
        chunk_size=75,
        threshold=0.72,
    )
    header = "| Area | Source | Example question |"
    separator = "|---|---|---|"
    rows = [
        f"| Area {index} | source-{index}.md | How does scenario {index} work? |"
        for index in range(1, 9)
    ]
    chunks = strategy.chunk("\n".join([header, separator, *rows]))
    counter = OCIChonkieEmbeddings(embeddings, dimension=3)

    assert len(chunks) > 1
    assert all(chunk.splitlines()[:2] == [header, separator] for chunk in chunks)
    assert all(counter.count_tokens(chunk) <= 75 for chunk in chunks)
    for row in rows:
        assert sum(row in chunk for chunk in chunks) == 1


def test_table_syntax_inside_fenced_code_is_not_treated_as_a_table() -> None:
    strategy = SemanticChunkingStrategy(
        FakeEmbeddings(),
        dimension=3,
        chunk_size=100,
        threshold=0.72,
    )
    text = """Example

```markdown
| Header | Value |
|---|---|
| one | two |
```"""

    assert strategy._markdown_table_spans(text) == []


def test_small_fenced_code_block_stays_whole() -> None:
    strategy = SemanticChunkingStrategy(
        FakeEmbeddings(),
        dimension=3,
        chunk_size=100,
        threshold=0.72,
    )
    text = """Authentication example

```python
def build_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
```"""

    assert strategy.chunk(text) == [text]


def test_large_python_block_splits_at_complete_function_boundaries() -> None:
    embeddings = FakeEmbeddings()
    strategy = SemanticChunkingStrategy(
        embeddings,
        dimension=3,
        chunk_size=48,
        threshold=0.72,
    )
    functions = [
        "\n".join(
            [
                f"def handler_{index}(request):",
                f"    result = process_{index}(request)",
                "    audit(result)",
                "    return result",
            ]
        )
        for index in range(1, 4)
    ]
    block = f"```python\n{'\n\n'.join(functions)}\n```"
    chunks = strategy.chunk(block)
    counter = OCIChonkieEmbeddings(embeddings, dimension=3)

    assert len(chunks) > 1
    assert all(chunk.startswith("```python\n") for chunk in chunks)
    assert all(chunk.endswith("\n```") for chunk in chunks)
    assert all(counter.count_tokens(chunk) <= 48 for chunk in chunks)
    for function in functions:
        assert sum(function in chunk for chunk in chunks) == 1


def test_unknown_code_language_splits_only_between_complete_lines() -> None:
    embeddings = FakeEmbeddings()
    strategy = SemanticChunkingStrategy(
        embeddings,
        dimension=3,
        chunk_size=42,
        threshold=0.72,
    )
    lines = [
        f"EVENT {index} status OK component worker detail completed normally"
        for index in range(1, 7)
    ]
    chunks = strategy.chunk(f"```customlog\n{'\n'.join(lines)}\n```")
    counter = OCIChonkieEmbeddings(embeddings, dimension=3)

    assert len(chunks) > 1
    assert all(chunk.startswith("```customlog\n") for chunk in chunks)
    assert all(chunk.endswith("\n```") for chunk in chunks)
    assert all(counter.count_tokens(chunk) <= 42 for chunk in chunks)
    for line in lines:
        assert sum(line in chunk for chunk in chunks) == 1
