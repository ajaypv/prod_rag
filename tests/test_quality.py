import json

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from prodrag.domain import RetrievedCandidate
from prodrag.quality import RAGQualityJudge


def test_quality_judge_scores_reference_and_evidence_separately() -> None:
    model_result = json.dumps(
        {
            "correctness": 0.25,
            "completeness": 0.5,
            "faithfulness": 0.0,
            "citation_correctness": 0.0,
            "reason": "The generated retention period contradicts the source.",
        }
    )
    judge = RAGQualityJudge(FakeListChatModel(responses=[model_result]))
    context = RetrievedCandidate(
        document=Document(
            page_content="Events are retained for 24 hours.",
            metadata={"document_id": "streaming", "section": "Replay"},
        ),
        hybrid_score=0.9,
        rerank_score=0.95,
    )

    scores = judge.evaluate(
        question="How long are events retained?",
        reference_answer="Events are retained for 24 hours.",
        generated_answer="Events are retained for 72 hours. [S1]",
        contexts=[context],
    )

    assert scores.correctness == 0.25
    assert scores.faithfulness == 0.0
    assert scores.citation_correctness == 0.0


def test_quality_judge_retries_invalid_json() -> None:
    valid = json.dumps(
        {
            "correctness": 1.0,
            "completeness": 1.0,
            "faithfulness": 1.0,
            "citation_correctness": 1.0,
            "reason": "Supported.",
        }
    )
    judge = RAGQualityJudge(
        FakeListChatModel(responses=["not json", valid]), retry_attempts=2
    )

    scores = judge.evaluate(
        question="Question?",
        reference_answer="Answer.",
        generated_answer="Answer. [S1]",
        contexts=[],
    )

    assert scores.correctness == 1.0
