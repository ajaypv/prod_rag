from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from prodrag.deepeval_evaluation import OCIChatDeepEvalModel, evaluate_deepeval
from prodrag.evaluation import RAGEvaluationRecord


class Verdict(BaseModel):
    verdict: str


class FakeChatModel:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(content='Result: {"verdict":"yes"}')

    async def ainvoke(self, prompt: str):
        self.prompts.append(prompt)
        return SimpleNamespace(content=[{"type": "text", "text": '{"verdict":"yes"}'}])


def test_oci_model_validates_deepeval_structured_output() -> None:
    chat_model = FakeChatModel()
    judge = OCIChatDeepEvalModel(
        chat_model,  # type: ignore[arg-type]
        model_name="oci-test-model",
        retry_attempts=1,
    )

    result = judge.generate("Judge this answer", schema=Verdict)

    assert result == Verdict(verdict="yes")
    assert "JSON Schema" in chat_model.prompts[0]
    assert judge.get_model_name() == "oci-test-model"


def test_oci_model_reports_invalid_structured_output() -> None:
    class InvalidChatModel(FakeChatModel):
        def invoke(self, prompt: str):
            self.prompts.append(prompt)
            return SimpleNamespace(content='{"wrong_field":"value"}')

    judge = OCIChatDeepEvalModel(
        InvalidChatModel(),  # type: ignore[arg-type]
        model_name="oci-test-model",
        retry_attempts=1,
    )

    with pytest.raises(
        RuntimeError,
        match=r"failed after 1 attempts.*response did not match Verdict.*response_preview",
    ):
        judge.generate("Judge this answer", schema=Verdict)


class FakeMetric:
    def __init__(self, score: float, reason: str) -> None:
        self.configured_score = score
        self.configured_reason = reason
        self.score: float | None = None
        self.reason: str | None = None

    def measure(self, test_case) -> float:
        assert test_case.expected_output == "Golden answer"
        assert test_case.retrieval_context == ["Supporting context"]
        self.score = self.configured_score
        self.reason = self.configured_reason
        return self.score


class FakeJudge:
    def get_model_name(self) -> str:
        return "fake-judge"


class FailingMetric:
    score = None
    reason = None

    def measure(self, test_case) -> float:
        raise ValueError("judge returned truncated JSON")


def test_deepeval_metric_failure_names_case_question_and_cause(monkeypatch) -> None:
    monkeypatch.setattr(
        "prodrag.deepeval_evaluation._build_metrics",
        lambda _judge: (("faithfulness", FailingMetric()),),
    )
    events: list[tuple[str, dict[str, object]]] = []
    record = RAGEvaluationRecord(
        question="What is the API limit?",
        expected_output="The limit is 100.",
        actual_output="The limit is 100.",
        retrieval_context=("The API limit is 100.",),
        answered=True,
    )

    with pytest.raises(
        RuntimeError,
        match=r"faithfulness.*golden case 1.*What is the API limit.*truncated JSON",
    ):
        evaluate_deepeval(
            [record],
            FakeJudge(),  # type: ignore[arg-type]
            progress=lambda event, detail: events.append((event, detail)),
        )

    assert events[-1][0] == "deepeval_metric_failed"
    assert "truncated JSON" in str(events[-1][1]["error"])


def test_deepeval_aggregates_scores_and_penalizes_false_abstention(monkeypatch) -> None:
    configured = (
        ("contextual_recall", 0.8),
        ("contextual_precision", 0.6),
        ("faithfulness", 1.0),
        ("answer_relevancy", 0.9),
    )
    monkeypatch.setattr(
        "prodrag.deepeval_evaluation._build_metrics",
        lambda _judge: tuple(
            (name, FakeMetric(score, f"{name} reason")) for name, score in configured
        ),
    )

    events: list[tuple[str, dict[str, object]]] = []
    metrics = evaluate_deepeval(
        [
            RAGEvaluationRecord(
                question="Answered question",
                expected_output="Golden answer",
                actual_output="Generated answer",
                retrieval_context=("Supporting context",),
                answered=True,
            ),
            RAGEvaluationRecord(
                question="False abstention",
                expected_output="Golden answer",
                actual_output="I do not know",
                retrieval_context=(),
                answered=False,
            ),
        ],
        FakeJudge(),  # type: ignore[arg-type]
        progress=lambda event, detail: events.append((event, detail)),
    )

    assert metrics["deepeval_labeled_questions"] == 2
    assert metrics["deepeval_contextual_recall"] == 0.4
    assert metrics["deepeval_contextual_precision"] == 0.3
    assert metrics["deepeval_faithfulness"] == 0.5
    assert metrics["deepeval_answer_relevancy"] == 0.45
    assert metrics["deepeval_judge_model"] == "fake-judge"
    assert metrics["deepeval_case_results"][1]["scores"]["faithfulness"] == 0.0
    assert events[0][0] == "deepeval_case_started"
    assert any(
        event == "deepeval_metric_completed"
        and detail["metric"] == "faithfulness"
        and detail["reason"] == "faithfulness reason"
        for event, detail in events
    )
