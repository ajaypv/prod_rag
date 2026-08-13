from __future__ import annotations

import json
from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from prodrag.domain import RetrievedCandidate
from prodrag.prompts import QUALITY_EVALUATION_PROMPT


class QualityScores(BaseModel):
    """Independent generation-quality dimensions used by the offline golden evaluation."""

    correctness: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    faithfulness: float = Field(ge=0.0, le=1.0)
    citation_correctness: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=1_000)


class RAGQualityJudge:
    """Score generated answers against both golden facts and retrieved evidence.

    This judge is intentionally an evaluation component, not part of the online answer path.
    It therefore improves release gating without adding another model call to every user query.
    """

    def __init__(self, chat_model: BaseChatModel, *, retry_attempts: int = 3) -> None:
        self._chain = QUALITY_EVALUATION_PROMPT | chat_model | StrOutputParser()
        self.retry_attempts = retry_attempts

    def evaluate(
        self,
        *,
        question: str,
        reference_answer: str,
        generated_answer: str,
        contexts: Sequence[RetrievedCandidate],
    ) -> QualityScores:
        sources = [
            {
                "source_id": f"S{index}",
                "document_id": str(item.document.metadata.get("document_id", "")),
                "section": str(item.document.metadata.get("section", "")),
                "content": item.document.page_content,
            }
            for index, item in enumerate(contexts, start=1)
        ]
        evaluation_input = json.dumps(
            {
                "question": question,
                "reference_answer": reference_answer,
                "generated_answer": generated_answer,
                "sources": sources,
            },
            ensure_ascii=False,
        )
        last_error: Exception | None = None
        for _ in range(self.retry_attempts):
            try:
                raw_result = self._chain.invoke(
                    {"evaluation_input": evaluation_input}
                ).strip()
                return QualityScores.model_validate_json(_extract_json_object(raw_result))
            except Exception as exc:
                last_error = exc
        raise RuntimeError("RAG quality evaluation failed after retries") from last_error


def _extract_json_object(raw_result: str) -> str:
    """Accept harmless fences/prose while still requiring one valid JSON object."""
    start = raw_result.find("{")
    end = raw_result.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Quality judge did not return a JSON object")
    return raw_result[start : end + 1]
