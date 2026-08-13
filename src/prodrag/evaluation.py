from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from prodrag.container import get_quality_judge, get_query_service, get_retrieval_service
from prodrag.models import QueryRequest, TicketCategory
from prodrag.quality import RAGQualityJudge


def _p95_ms(durations: list[float]) -> float:
    if not durations:
        return 0.0
    ordered = sorted(durations)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return round(ordered[index] * 1_000, 3)


class EvaluationCase(BaseModel):
    question: str
    expected_answer: str | None = None
    expected_document_ids: list[str] = Field(default_factory=list)
    expected_context_phrases: list[str] = Field(default_factory=list)
    expected_answerable: bool = True
    tenant_id: str = "default"
    product: str | None = None
    version: str | None = None
    expected_category: TicketCategory | None = None
    expected_human_review: bool | None = None

    @model_validator(mode="after")
    def validate_labels(self):
        if self.expected_answerable and not self.expected_document_ids:
            raise ValueError("Answerable rows require expected_document_ids")
        if not self.expected_answerable and self.expected_context_phrases:
            raise ValueError("Unanswerable rows cannot require context phrases")
        return self


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                cases.append(EvaluationCase.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"Invalid evaluation row at line {line_number}: {exc}") from exc
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    return cases


def evaluate(cases: list[EvaluationCase]) -> dict[str, float | int | None]:
    service = get_retrieval_service()
    recalls: list[float] = []
    precisions: list[float] = []
    reciprocal_ranks: list[float] = []
    hits = 0
    unanswerable_count = 0
    correct_abstentions = 0
    durations: list[float] = []
    context_precisions: list[float] = []
    context_recalls: list[float] = []
    for case in cases:
        started = time.perf_counter()
        results = service.retrieve(
            case.question,
            tenant_id=case.tenant_id,
            product=case.product,
            version=case.version,
        )
        durations.append(time.perf_counter() - started)
        ranked_ids = [str(item.document.metadata.get("document_id")) for item in results]
        if not case.expected_answerable:
            unanswerable_count += 1
            correct_abstentions += int(not ranked_ids)
            continue
        expected = set(case.expected_document_ids)
        returned = set(ranked_ids)
        found = expected.intersection(returned)
        recalls.append(len(found) / len(expected))
        precisions.append(len(found) / len(returned) if returned else 0.0)
        hits += int(bool(found))
        first_rank = next(
            (
                rank
                for rank, document_id in enumerate(ranked_ids, start=1)
                if document_id in expected
            ),
            None,
        )
        reciprocal_ranks.append(1 / first_rank if first_rank else 0.0)
        if case.expected_context_phrases:
            phrases = [phrase.casefold() for phrase in case.expected_context_phrases]
            context_texts = [item.document.page_content.casefold() for item in results]
            relevant_contexts = sum(
                any(phrase in context for phrase in phrases) for context in context_texts
            )
            found_phrases = sum(
                any(phrase in context for context in context_texts) for phrase in phrases
            )
            context_precisions.append(
                relevant_contexts / len(context_texts) if context_texts else 0.0
            )
            context_recalls.append(found_phrases / len(phrases))
    count = len(recalls)
    return {
        "questions": len(cases),
        "answerable_questions": count,
        "unanswerable_questions": unanswerable_count,
        "hit_rate": hits / count if count else 1.0,
        "mean_recall": sum(recalls) / count if count else 1.0,
        "mean_precision": sum(precisions) / count if count else 1.0,
        "mrr": sum(reciprocal_ranks) / count if count else 1.0,
        "context_labeled_questions": len(context_precisions),
        "mean_context_precision": (
            sum(context_precisions) / len(context_precisions)
            if context_precisions
            else None
        ),
        "mean_context_recall": (
            sum(context_recalls) / len(context_recalls) if context_recalls else None
        ),
        "empty_retrieval_rate": (
            correct_abstentions / unanswerable_count if unanswerable_count else 1.0
        ),
        "retrieval_p95_ms": _p95_ms(durations),
    }


def evaluate_answers(
    cases: list[EvaluationCase], *, quality_judge: RAGQualityJudge | None = None
) -> dict[str, float | int | None]:
    service = get_query_service()
    answerability_matches = 0
    answerable_count = 0
    unanswerable_count = 0
    correct_abstentions = 0
    cited_expected_document = 0
    cited_answers = 0
    category_labels = 0
    category_matches = 0
    review_labels = 0
    review_matches = 0
    durations: list[float] = []
    correctness_scores: list[float] = []
    completeness_scores: list[float] = []
    faithfulness_scores: list[float] = []
    citation_correctness_scores: list[float] = []

    if quality_judge is None and any(
        case.expected_answerable and case.expected_answer for case in cases
    ):
        quality_judge = get_quality_judge()

    for case in cases:
        started = time.perf_counter()
        request = QueryRequest(
            question=case.question,
            tenant_id=case.tenant_id,
            product=case.product,
            version=case.version,
        )
        if hasattr(service, "query_with_evidence"):
            execution = service.query_with_evidence(request)
            response = execution.response
            contexts = execution.contexts
        else:
            response = service.query(request)
            contexts = ()
        durations.append(time.perf_counter() - started)
        answerability_matches += int(response.answered == case.expected_answerable)
        if case.expected_answerable:
            answerable_count += 1
            cited_ids = {citation.document_id for citation in response.citations}
            cited_answers += int(response.answered and bool(response.citations))
            cited_expected_document += int(
                response.answered
                and bool(set(case.expected_document_ids).intersection(cited_ids))
            )
        else:
            unanswerable_count += 1
            correct_abstentions += int(not response.answered)
        if case.expected_category is not None:
            category_labels += 1
            category_matches += int(response.category == case.expected_category)
        if case.expected_human_review is not None:
            review_labels += 1
            review_matches += int(
                response.requires_human_review == case.expected_human_review
            )
        if case.expected_answerable and case.expected_answer:
            if response.answered and quality_judge is not None:
                scores = quality_judge.evaluate(
                    question=case.question,
                    reference_answer=case.expected_answer,
                    generated_answer=response.answer,
                    contexts=contexts,
                )
                correctness_scores.append(scores.correctness)
                completeness_scores.append(scores.completeness)
                faithfulness_scores.append(scores.faithfulness)
                citation_correctness_scores.append(scores.citation_correctness)
            else:
                # An answerable golden question that the pipeline refused cannot receive
                # generation-quality credit merely because it failed safely.
                correctness_scores.append(0.0)
                completeness_scores.append(0.0)
                faithfulness_scores.append(0.0)
                citation_correctness_scores.append(0.0)

    return {
        "answerability_accuracy": answerability_matches / len(cases),
        "abstention_accuracy": (
            correct_abstentions / unanswerable_count if unanswerable_count else 1.0
        ),
        "citation_coverage": cited_answers / answerable_count if answerable_count else 1.0,
        "citation_document_hit_rate": (
            cited_expected_document / answerable_count if answerable_count else 1.0
        ),
        "category_accuracy": category_matches / category_labels if category_labels else None,
        "review_routing_accuracy": (
            review_matches / review_labels if review_labels else None
        ),
        "category_labeled_questions": category_labels,
        "review_labeled_questions": review_labels,
        "quality_labeled_questions": len(correctness_scores),
        "answer_correctness": _mean_or_none(correctness_scores),
        "answer_completeness": _mean_or_none(completeness_scores),
        "faithfulness": _mean_or_none(faithfulness_scores),
        "citation_correctness": _mean_or_none(citation_correctness_scores),
        "end_to_end_p95_ms": _p95_ms(durations),
    }


def _mean_or_none(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _passes_optional_gate(value: object, threshold: float) -> bool:
    """A requested gate fails when its dataset has no corresponding labels."""
    if threshold <= 0:
        return True
    return isinstance(value, int | float) and value >= threshold


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate prodRAG retrieval against JSONL labels")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--min-recall", type=float, default=0.95)
    parser.add_argument(
        "--min-precision",
        type=float,
        default=0.0,
        help="Minimum macro document-level precision for answerable questions (disabled at 0)",
    )
    parser.add_argument("--min-hit-rate", type=float, default=0.95)
    parser.add_argument("--min-context-precision", type=float, default=0.0)
    parser.add_argument("--min-context-recall", type=float, default=0.0)
    parser.add_argument("--end-to-end", action="store_true")
    parser.add_argument("--min-answerability", type=float, default=0.0)
    parser.add_argument("--min-citation-hit-rate", type=float, default=0.0)
    parser.add_argument("--min-abstention", type=float, default=0.0)
    parser.add_argument("--min-answer-correctness", type=float, default=0.0)
    parser.add_argument("--min-answer-completeness", type=float, default=0.0)
    parser.add_argument("--min-faithfulness", type=float, default=0.0)
    parser.add_argument("--min-citation-correctness", type=float, default=0.0)
    args = parser.parse_args()
    if not args.end_to_end and any(
        threshold > 0
        for threshold in (
            args.min_answerability,
            args.min_citation_hit_rate,
            args.min_abstention,
            args.min_answer_correctness,
            args.min_answer_completeness,
            args.min_faithfulness,
            args.min_citation_correctness,
        )
    ):
        parser.error("answer, citation, and abstention gates require --end-to-end")
    cases = load_cases(args.dataset)
    metrics = evaluate(cases)
    if args.end_to_end:
        metrics.update(evaluate_answers(cases))
    print(json.dumps(metrics, indent=2))
    passed = (
        metrics["mean_recall"] >= args.min_recall
        and metrics["mean_precision"] >= args.min_precision
        and metrics["hit_rate"] >= args.min_hit_rate
        and _passes_optional_gate(
            metrics["mean_context_precision"], args.min_context_precision
        )
        and _passes_optional_gate(metrics["mean_context_recall"], args.min_context_recall)
    )
    if args.end_to_end:
        passed = bool(
            passed
            and metrics["answerability_accuracy"] >= args.min_answerability
            and metrics["citation_document_hit_rate"] >= args.min_citation_hit_rate
            and metrics["abstention_accuracy"] >= args.min_abstention
            and _passes_optional_gate(
                metrics["answer_correctness"], args.min_answer_correctness
            )
            and _passes_optional_gate(
                metrics["answer_completeness"], args.min_answer_completeness
            )
            and _passes_optional_gate(metrics["faithfulness"], args.min_faithfulness)
            and _passes_optional_gate(
                metrics["citation_correctness"], args.min_citation_correctness
            )
        )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
