from types import SimpleNamespace

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
    )

    assert metrics["deepeval_labeled_questions"] == 2
    assert metrics["deepeval_contextual_recall"] == 0.4
    assert metrics["deepeval_contextual_precision"] == 0.3
    assert metrics["deepeval_faithfulness"] == 0.5
    assert metrics["deepeval_answer_relevancy"] == 0.45
    assert metrics["deepeval_judge_model"] == "fake-judge"
    assert metrics["deepeval_case_results"][1]["scores"]["faithfulness"] == 0.0
