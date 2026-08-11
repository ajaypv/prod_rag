from langchain_core.documents import Document

from prodrag.domain import RetrievedCandidate
from prodrag.evaluation import EvaluationCase, evaluate, evaluate_answers
from prodrag.models import (
    Citation,
    ConfidenceLevel,
    QueryResponse,
    TicketCategory,
)


class FakeRetrievalService:
    def retrieve(self, question: str, **_: object) -> list[RetrievedCandidate]:
        by_question = {
            "one": ["a", "unrelated"],
            "two": ["b", "c"],
            "none": [],
        }
        return [
            RetrievedCandidate(
                Document(page_content=document_id, metadata={"document_id": document_id}),
                hybrid_score=1.0,
            )
            for document_id in by_question[question]
        ]


def test_evaluate_reports_macro_document_precision(monkeypatch) -> None:
    monkeypatch.setattr("prodrag.evaluation.get_retrieval_service", FakeRetrievalService)

    metrics = evaluate(
        [
            EvaluationCase(question="one", expected_document_ids=["a"]),
            EvaluationCase(question="two", expected_document_ids=["b", "missing"]),
            EvaluationCase(question="none", expected_answerable=False),
        ]
    )

    assert metrics["mean_recall"] == 0.75
    assert metrics["mean_precision"] == 0.5
    assert metrics["hit_rate"] == 1.0
    assert metrics["empty_retrieval_rate"] == 1.0
    assert metrics["retrieval_p95_ms"] >= 0


class FakeQueryService:
    def query(self, request):
        if request.question == "none":
            return QueryResponse(
                request_id="r-none",
                category=TicketCategory.OTHER,
                confidence=ConfidenceLevel.LOW,
                requires_human_review=True,
                answered=False,
                answer="Human review required",
            )
        return QueryResponse(
            request_id=f"r-{request.question}",
            category=TicketCategory.BILLING,
            confidence=ConfidenceLevel.HIGH,
            requires_human_review=False,
            answered=True,
            answer="Grounded answer [S1]",
            citations=[
                Citation(
                    source_id="S1",
                    document_id="a" if request.question == "one" else "b",
                    title="Doc",
                    section="Section",
                    source_name="doc.md",
                    relevance_score=0.9,
                )
            ],
        )


def test_evaluate_answers_measures_real_abstention_and_citations(monkeypatch) -> None:
    monkeypatch.setattr("prodrag.evaluation.get_query_service", FakeQueryService)

    metrics = evaluate_answers(
        [
            EvaluationCase(question="one", expected_document_ids=["a"]),
            EvaluationCase(question="two", expected_document_ids=["b"]),
            EvaluationCase(question="none", expected_answerable=False),
        ]
    )

    assert metrics["answerability_accuracy"] == 1.0
    assert metrics["abstention_accuracy"] == 1.0
    assert metrics["citation_coverage"] == 1.0
    assert metrics["citation_document_hit_rate"] == 1.0
    assert metrics["end_to_end_p95_ms"] >= 0
