from langchain_core.documents import Document

from prodrag.domain import RetrievedCandidate
from prodrag.evaluation import (
    EvaluationCase,
    RAGEvaluationRecord,
    evaluate,
    evaluate_answers,
)
from prodrag.models import (
    Citation,
    ConfidenceLevel,
    QueryResponse,
    TicketCategory,
)
from prodrag.quality import QualityScores
from prodrag.querying import QueryExecution


class FakeRetrievalService:
    def retrieve(self, question: str, **_: object) -> list[RetrievedCandidate]:
        by_question = {
            "one": ["a", "unrelated"],
            "two": ["b", "c"],
            "none": [],
        }
        return [
            RetrievedCandidate(
                Document(
                    page_content=(
                        "expected supporting fact" if document_id == "a" else "noise"
                    ),
                    metadata={"document_id": document_id},
                ),
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


def test_evaluate_reports_passage_precision_and_recall(monkeypatch) -> None:
    monkeypatch.setattr("prodrag.evaluation.get_retrieval_service", FakeRetrievalService)

    metrics = evaluate(
        [
            EvaluationCase(
                question="one",
                expected_document_ids=["a"],
                expected_context_phrases=["expected supporting fact", "missing fact"],
            )
        ]
    )

    assert metrics["context_labeled_questions"] == 1
    assert metrics["mean_context_precision"] == 0.5
    assert metrics["mean_context_recall"] == 0.5


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

    def query_with_evidence(self, request):
        response = self.query(request)
        contexts = (
            RetrievedCandidate(
                Document(
                    page_content="Grounded answer.",
                    metadata={"document_id": "a", "section": "Section"},
                ),
                hybrid_score=0.9,
            ),
        )
        return QueryExecution(response=response, contexts=contexts)


class FakeQualityJudge:
    def evaluate(self, **_):
        return QualityScores(
            correctness=0.9,
            completeness=0.8,
            faithfulness=1.0,
            citation_correctness=1.0,
            reason="Supported",
        )


def test_evaluate_answers_measures_real_abstention_and_citations(monkeypatch) -> None:
    monkeypatch.setattr("prodrag.evaluation.get_query_service", FakeQueryService)
    records: list[RAGEvaluationRecord] = []

    metrics = evaluate_answers(
        [
            EvaluationCase(
                question="one",
                expected_document_ids=["a"],
                expected_answer="Grounded answer.",
            ),
            EvaluationCase(question="two", expected_document_ids=["b"]),
            EvaluationCase(question="none", expected_answerable=False),
        ],
        quality_judge=FakeQualityJudge(),
        records=records,
    )

    assert metrics["answerability_accuracy"] == 1.0
    assert metrics["abstention_accuracy"] == 1.0
    assert metrics["citation_coverage"] == 1.0
    assert metrics["citation_document_hit_rate"] == 1.0
    assert metrics["quality_labeled_questions"] == 1
    assert metrics["answer_correctness"] == 0.9
    assert metrics["answer_completeness"] == 0.8
    assert metrics["faithfulness"] == 1.0
    assert metrics["citation_correctness"] == 1.0
    assert metrics["end_to_end_p95_ms"] >= 0
    assert records == [
        RAGEvaluationRecord(
            question="one",
            expected_output="Grounded answer.",
            actual_output="Grounded answer [S1]",
            retrieval_context=("Grounded answer.",),
            answered=True,
        )
    ]
