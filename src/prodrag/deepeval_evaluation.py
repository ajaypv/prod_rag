from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from prodrag.evaluation import RAGEvaluationRecord


class OCIChatDeepEvalModel(DeepEvalBaseLLM):
    """Expose the configured LangChain OCI chat model as a DeepEval judge.

    DeepEval asks its judge for Pydantic-shaped JSON. OCI's LangChain adapter
    returns a regular AI message, so this class adds the requested JSON schema,
    extracts the message text, validates it, and returns the schema instance
    expected by DeepEval 4.x.
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        *,
        model_name: str,
        retry_attempts: int = 3,
    ) -> None:
        self.chat_model = chat_model
        self.retry_attempts = retry_attempts
        super().__init__(model=model_name)

    def load_model(self) -> BaseChatModel:
        return self.chat_model

    def get_model_name(self) -> str:
        return self.name

    def supports_structured_outputs(self) -> bool:
        return True

    def supports_json_mode(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        request = _with_schema(prompt, schema)
        return self._run_with_retries(
            lambda: _parse_response(self.model.invoke(request), schema)
        )

    async def a_generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        request = _with_schema(prompt, schema)
        last_error: Exception | None = None
        for _ in range(self.retry_attempts):
            try:
                return _parse_response(await self.model.ainvoke(request), schema)
            except Exception as exc:  # DeepEval should receive a final, contextual failure.
                last_error = exc
        raise RuntimeError(
            f"OCI DeepEval judge failed after {self.retry_attempts} attempts"
        ) from last_error

    def _run_with_retries(self, operation: Callable[[], str | BaseModel]) -> str | BaseModel:
        last_error: Exception | None = None
        for _ in range(self.retry_attempts):
            try:
                return operation()
            except Exception as exc:  # Model and schema failures are both retryable offline.
                last_error = exc
        raise RuntimeError(
            f"OCI DeepEval judge failed after {self.retry_attempts} attempts"
        ) from last_error


def evaluate_deepeval(
    records: list[RAGEvaluationRecord],
    judge: DeepEvalBaseLLM,
) -> dict[str, object]:
    """Score completed RAG executions with four complementary DeepEval metrics.

    Contextual recall and precision evaluate the retriever against the golden
    answer. Faithfulness and answer relevancy evaluate the generated answer.
    Existing deterministic document metrics and unanswerable-case checks stay
    in ``evaluation.py`` because they do not need an LLM judge.
    """

    score_groups: dict[str, list[float]] = {
        "contextual_recall": [],
        "contextual_precision": [],
        "faithfulness": [],
        "answer_relevancy": [],
    }
    case_results: list[dict[str, object]] = []

    for index, record in enumerate(records, start=1):
        if not record.answered or not record.retrieval_context:
            detail = (
                "The pipeline abstained on an answerable golden question."
                if not record.answered
                else "The pipeline answered without retrieval context."
            )
            scores = dict.fromkeys(score_groups, 0.0)
            reasons = dict.fromkeys(score_groups, detail)
        else:
            test_case = LLMTestCase(
                input=record.question,
                actual_output=record.actual_output,
                expected_output=record.expected_output,
                retrieval_context=list(record.retrieval_context),
            )
            scores: dict[str, float] = {}
            reasons: dict[str, str | None] = {}
            for name, metric in _build_metrics(judge):
                try:
                    metric.measure(test_case)
                except Exception as exc:
                    raise RuntimeError(
                        f"DeepEval metric {name!r} failed for golden case {index}"
                    ) from exc
                score = float(metric.score or 0.0)
                scores[name] = score
                reasons[name] = metric.reason

        for name, score in scores.items():
            score_groups[name].append(score)
        case_results.append(
            {
                "case": index,
                "question": record.question,
                "answered": record.answered,
                "scores": scores,
                "reasons": reasons,
            }
        )

    return {
        "deepeval_labeled_questions": len(records),
        "deepeval_judge_model": judge.get_model_name(),
        "deepeval_contextual_recall": _mean(score_groups["contextual_recall"]),
        "deepeval_contextual_precision": _mean(score_groups["contextual_precision"]),
        "deepeval_faithfulness": _mean(score_groups["faithfulness"]),
        "deepeval_answer_relevancy": _mean(score_groups["answer_relevancy"]),
        "deepeval_case_results": case_results,
    }


def _build_metrics(judge: DeepEvalBaseLLM) -> tuple[tuple[str, Any], ...]:
    options = {
        "model": judge,
        "threshold": 0.0,
        "include_reason": True,
        "async_mode": False,
    }
    return (
        ("contextual_recall", ContextualRecallMetric(**options)),
        ("contextual_precision", ContextualPrecisionMetric(**options)),
        ("faithfulness", FaithfulnessMetric(**options)),
        ("answer_relevancy", AnswerRelevancyMetric(**options)),
    )


def _with_schema(prompt: str, schema: type[BaseModel] | None) -> str:
    if schema is None:
        return prompt
    schema_json = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    return (
        f"{prompt}\n\nReturn only one valid JSON object matching this JSON Schema. "
        f"Do not use Markdown fences or add commentary.\nJSON Schema: {schema_json}"
    )


def _parse_response(message: object, schema: type[BaseModel] | None) -> str | BaseModel:
    text = _message_text(message)
    if schema is None:
        return text
    return schema.model_validate_json(_extract_json_object(text))


def _message_text(message: object) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        if parts:
            return "\n".join(parts).strip()
    raise TypeError("OCI judge returned an unsupported message content type")


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("OCI judge did not return a JSON object")
    return text[start : end + 1]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
