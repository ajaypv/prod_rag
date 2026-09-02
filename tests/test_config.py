import pytest
from pydantic import ValidationError

from prodrag.config import Settings


def test_parent_and_answer_budget_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "RAG_PARENT_MAX_CHARS",
        "RAG_PARENT_MAX_TOKENS",
        "RAG_CHUNK_SIZE_TOKENS",
        "RAG_CONTEXT_CHAR_BUDGET",
        "RAG_CONTEXT_TOKEN_BUDGET",
        "RAG_PARENT_NEIGHBOR_COUNT",
        "RAG_EXPANDED_PARENT_MAX_TOKENS",
        "RAG_EVAL_MAX_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)

    assert settings.parent_max_chars == 8_000
    assert settings.parent_max_tokens == 2_000
    assert settings.chunk_size_tokens == 450
    assert settings.context_char_budget == 30_000
    assert settings.context_token_budget == 7_500
    assert settings.parent_neighbor_count == 1
    assert settings.expanded_parent_max_tokens == 3_000
    assert settings.oci_eval_max_tokens == 4_000


def test_neighbor_expansion_cannot_be_smaller_than_one_parent() -> None:
    with pytest.raises(ValidationError, match="RAG_EXPANDED_PARENT_MAX_TOKENS"):
        Settings(
            _env_file=None,
            parent_max_tokens=4_000,
            expanded_parent_max_tokens=3_000,
        )
