from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import textwrap
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from prodrag.container import get_quality_judge, get_query_service, get_retrieval_service
from prodrag.models import QueryRequest, TicketCategory
from prodrag.quality import RAGQualityJudge

ProgressCallback = Callable[[str, dict[str, object]], None]


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


@dataclass(frozen=True)
class RAGEvaluationRecord:
    """One completed answerable query prepared for external semantic evaluators.

    The record contains the exact answer and parent contexts used by the query
    pipeline. Keeping this transport type independent of DeepEval means the
    normal evaluator and production package can still be imported when the
    optional development dependency is not installed.
    """

    question: str
    expected_output: str
    actual_output: str
    retrieval_context: tuple[str, ...]
    answered: bool


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


def evaluate(
    cases: list[EvaluationCase],
    *,
    case_results: list[dict[str, object]] | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, float | int | None]:
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
    for case_index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        results = service.retrieve(
            case.question,
            tenant_id=case.tenant_id,
            product=case.product,
            version=case.version,
        )
        durations.append(time.perf_counter() - started)
        ranked_ids = [str(item.document.metadata.get("document_id")) for item in results]
        duration_ms = round(durations[-1] * 1_000, 3)
        if not case.expected_answerable:
            unanswerable_count += 1
            correct_abstentions += int(not ranked_ids)
            detail = {
                "case": case_index,
                "total": len(cases),
                "question": case.question,
                "expected_answerable": False,
                "expected_document_ids": [],
                "retrieved_document_ids": ranked_ids,
                "empty_retrieval": not ranked_ids,
                "duration_ms": duration_ms,
            }
            if case_results is not None:
                case_results.append(detail)
            if progress is not None:
                progress("retrieval_case", detail)
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
        context_precision: float | None = None
        context_recall: float | None = None
        if case.expected_context_phrases:
            phrases = [phrase.casefold() for phrase in case.expected_context_phrases]
            context_texts = [item.document.page_content.casefold() for item in results]
            relevant_contexts = sum(
                any(phrase in context for phrase in phrases) for context in context_texts
            )
            found_phrases = sum(
                any(phrase in context for context in context_texts) for phrase in phrases
            )
            context_precision = relevant_contexts / len(context_texts) if context_texts else 0.0
            context_recall = found_phrases / len(phrases)
            context_precisions.append(context_precision)
            context_recalls.append(context_recall)
        detail = {
            "case": case_index,
            "total": len(cases),
            "question": case.question,
            "expected_answerable": True,
            "expected_document_ids": case.expected_document_ids,
            "retrieved_document_ids": ranked_ids,
            "recall": recalls[-1],
            "precision": precisions[-1],
            "reciprocal_rank": reciprocal_ranks[-1],
            "context_precision": context_precision,
            "context_recall": context_recall,
            "duration_ms": duration_ms,
        }
        if case_results is not None:
            case_results.append(detail)
        if progress is not None:
            progress("retrieval_case", detail)
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
    cases: list[EvaluationCase],
    *,
    quality_judge: RAGQualityJudge | None = None,
    records: list[RAGEvaluationRecord] | None = None,
    case_results: list[dict[str, object]] | None = None,
    progress: ProgressCallback | None = None,
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

    for case_index, case in enumerate(cases, start=1):
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
        quality_scores: dict[str, float] | None = None
        if case.expected_answerable and case.expected_answer:
            if records is not None:
                records.append(
                    RAGEvaluationRecord(
                        question=case.question,
                        expected_output=case.expected_answer,
                        actual_output=response.answer,
                        retrieval_context=tuple(
                            context.document.page_content for context in contexts
                        ),
                        answered=response.answered,
                    )
                )
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
                quality_scores = {
                    "correctness": scores.correctness,
                    "completeness": scores.completeness,
                    "faithfulness": scores.faithfulness,
                    "citation_correctness": scores.citation_correctness,
                }
            else:
                # An answerable golden question that the pipeline refused cannot receive
                # generation-quality credit merely because it failed safely.
                correctness_scores.append(0.0)
                completeness_scores.append(0.0)
                faithfulness_scores.append(0.0)
                citation_correctness_scores.append(0.0)
                quality_scores = {
                    "correctness": 0.0,
                    "completeness": 0.0,
                    "faithfulness": 0.0,
                    "citation_correctness": 0.0,
                }
        detail = {
            "case": case_index,
            "total": len(cases),
            "question": case.question,
            "expected_answerable": case.expected_answerable,
            "expected_output": case.expected_answer,
            "answered": response.answered,
            "actual_output": response.answer,
            "cited_document_ids": [citation.document_id for citation in response.citations],
            "retrieval_context": [context.document.page_content for context in contexts],
            "quality_scores": quality_scores,
            "duration_ms": round(durations[-1] * 1_000, 3),
        }
        if case_results is not None:
            case_results.append(detail)
        if progress is not None:
            progress("answer_case", detail)

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _gate_results(
    metrics: dict[str, object],
    thresholds: dict[str, float],
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for metric, threshold in thresholds.items():
        value = metrics.get(metric)
        enabled = threshold > 0
        passed = not enabled or (
            isinstance(value, int | float) and not isinstance(value, bool) and value >= threshold
        )
        results[metric] = {
            "value": value,
            "minimum": threshold,
            "enabled": enabled,
            "passed": passed,
        }
    return results


def _evaluation_metadata(dataset: Path, variant: str) -> dict[str, object]:
    from prodrag.config import get_settings

    settings = get_settings()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "variant": variant,
        "git_sha": os.getenv("PRODRAG_EVAL_GIT_SHA", "unknown"),
        "dataset": str(dataset.resolve()),
        "dataset_sha256": _sha256_file(dataset),
        "corpus_manifest_sha256": os.getenv("PRODRAG_CORPUS_MANIFEST_SHA256"),
        "configuration": {
            "oci_embed_model": settings.oci_embed_model,
            "oci_embed_dimension": settings.oci_embed_dimension,
            "oci_rerank_enabled": settings.oci_rerank_enabled,
            "oci_rerank_model": settings.oci_rerank_model,
            "oci_chat_model": settings.oci_chat_model,
            "qdrant_mode": (
                "embedded_exact"
                if settings.qdrant_path
                else "server_hnsw"
                if settings.qdrant_hnsw_enabled
                else "server_exact"
            ),
            "qdrant_collection": settings.qdrant_collection,
            "bm25_model": settings.bm25_model,
            "parent_max_tokens": settings.parent_max_tokens,
            "parent_max_chars": settings.parent_max_chars,
            "chunk_size_tokens": settings.chunk_size_tokens,
            "semantic_threshold": settings.semantic_threshold,
            "retrieval_candidates": settings.retrieval_candidates,
            "final_contexts": settings.final_contexts,
        },
    }


def _console_text(value: object) -> str:
    text = " ".join(str(value).split())
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def _print_field(label: str, value: object, *, width: int = 110) -> None:
    prefix = f"  {label}: "
    text = _console_text(value)
    lines = textwrap.wrap(
        text,
        width=width,
        initial_indent=prefix,
        subsequent_indent=" " * len(prefix),
        break_long_words=False,
        break_on_hyphens=False,
    )
    print("\n".join(lines) if lines else prefix.rstrip(), flush=True)


def _format_documents(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(str(item) for item in value)


def _format_score(value: object) -> str:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"{value:.3f}"
    return "n/a"


def _console_progress(event: str, detail: dict[str, object]) -> None:
    if event == "retrieval_case":
        print(
            f"\n[Retrieval {detail['case']}/{detail['total']}]",
            flush=True,
        )
        _print_field("Question", detail["question"])
        _print_field(
            "Expected",
            "answerable" if detail["expected_answerable"] else "must abstain",
        )
        _print_field("Expected documents", _format_documents(detail["expected_document_ids"]))
        _print_field("Retrieved documents", _format_documents(detail["retrieved_document_ids"]))
        if detail["expected_answerable"]:
            _print_field(
                "Retrieval scores",
                (
                    f"recall={_format_score(detail.get('recall'))}, "
                    f"precision={_format_score(detail.get('precision'))}, "
                    f"MRR={_format_score(detail.get('reciprocal_rank'))}"
                ),
            )
        else:
            _print_field("Retrieval result", "PASS" if detail["empty_retrieval"] else "REVIEW")
        _print_field("Time", f"{detail['duration_ms']} ms")
        return

    if event == "answer_case":
        print(f"\n[Answer {detail['case']}/{detail['total']}]", flush=True)
        _print_field("Question", detail["question"])
        _print_field("Expected answer", detail.get("expected_output") or "must abstain")
        _print_field("AI response", detail["actual_output"])
        _print_field("Answered", detail["answered"])
        _print_field("Cited documents", _format_documents(detail["cited_document_ids"]))
        quality = detail.get("quality_scores")
        if isinstance(quality, dict):
            _print_field(
                "Existing quality judge",
                ", ".join(f"{name}={_format_score(score)}" for name, score in quality.items()),
            )
        _print_field("Time", f"{detail['duration_ms']} ms")
        return

    if event == "deepeval_case_started":
        print(f"\n[DeepEval {detail['case']}/{detail['total']}]", flush=True)
        _print_field("Question", detail["question"])
        _print_field("Expected answer", detail["expected_output"])
        _print_field("AI response", detail["actual_output"])
        _print_field("Judge context", f"{detail['context_count']} retrieved parent context(s)")
        return

    if event == "deepeval_metric_started":
        _print_field("Judging", str(detail["metric"]).replace("_", " "))
        return

    if event == "deepeval_metric_completed":
        metric = str(detail["metric"]).replace("_", " ")
        _print_field(metric, f"score={_format_score(detail['score'])}")
        _print_field("Judge reason", detail.get("reason") or "No reason returned")
        return

    if event == "deepeval_metric_failed":
        metric = str(detail["metric"]).replace("_", " ")
        _print_field("Judge failure", f"{metric} FAILED")
        _print_field("Cause", detail["error"])


def _print_summary(report: dict[str, object], output: Path | None) -> None:
    print("\n" + "=" * 72, flush=True)
    print("Evaluation summary", flush=True)
    print("=" * 72, flush=True)
    gates = report.get("gate_results", {})
    if isinstance(gates, dict):
        for name, raw in gates.items():
            if not isinstance(raw, dict) or not raw.get("enabled"):
                continue
            status = "PASS" if raw.get("passed") else "FAIL"
            print(
                f"  [{status}] {name}: {_format_score(raw.get('value'))} "
                f"(minimum {_format_score(raw.get('minimum'))})",
                flush=True,
            )
    print(f"\nOverall: {'PASS' if report.get('passed') else 'FAIL'}", flush=True)
    failed = report.get("failed_gates", [])
    if failed:
        _print_field("Failed gates", _format_documents(failed))
    if output is not None:
        _print_field("JSON report", output.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate prodRAG retrieval against JSONL labels")
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the complete machine-readable evaluation report to this JSON file",
    )
    parser.add_argument(
        "--variant",
        default=os.getenv("PRODRAG_EVAL_VARIANT", "candidate"),
        help="Variant label recorded in the report (for example baseline or candidate)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Write all gate results but return success so a later A/B comparison can decide",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print readable per-question retrieval, answer, and judge progress",
    )
    parser.add_argument(
        "--no-print-report",
        action="store_true",
        help="Do not print the complete JSON report to stdout (use with --output)",
    )
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
    parser.add_argument(
        "--deepeval",
        action="store_true",
        help=(
            "Run DeepEval contextual recall, contextual precision, faithfulness, "
            "and answer relevancy metrics using the configured OCI chat model"
        ),
    )
    parser.add_argument("--min-answerability", type=float, default=0.0)
    parser.add_argument("--min-citation-hit-rate", type=float, default=0.0)
    parser.add_argument("--min-abstention", type=float, default=0.0)
    parser.add_argument("--min-answer-correctness", type=float, default=0.0)
    parser.add_argument("--min-answer-completeness", type=float, default=0.0)
    parser.add_argument("--min-faithfulness", type=float, default=0.0)
    parser.add_argument("--min-citation-correctness", type=float, default=0.0)
    parser.add_argument("--min-deepeval-contextual-recall", type=float, default=0.0)
    parser.add_argument("--min-deepeval-contextual-precision", type=float, default=0.0)
    parser.add_argument("--min-deepeval-faithfulness", type=float, default=0.0)
    parser.add_argument("--min-deepeval-answer-relevancy", type=float, default=0.0)
    args = parser.parse_args()
    if args.deepeval and not args.end_to_end:
        parser.error("--deepeval requires --end-to-end")
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
    if args.deepeval and not any(
        case.expected_answerable and case.expected_answer for case in cases
    ):
        parser.error("--deepeval requires at least one answerable row with expected_answer")

    retrieval_case_results: list[dict[str, object]] = []
    answer_case_results: list[dict[str, object]] = []
    progress = _console_progress if args.verbose else None
    if args.verbose:
        print("=" * 72, flush=True)
        print(f"prodRAG local evaluation: {args.variant}", flush=True)
        print("=" * 72, flush=True)
        _print_field("Dataset", args.dataset.resolve())
        _print_field("Questions", len(cases))
    metrics: dict[str, object] = evaluate(
        cases,
        case_results=retrieval_case_results,
        progress=progress,
    )
    deepeval_records: list[RAGEvaluationRecord] = []
    if args.end_to_end:
        metrics.update(
            evaluate_answers(
                cases,
                records=deepeval_records if args.deepeval else None,
                case_results=answer_case_results,
                progress=progress,
            )
        )
    if args.deepeval:
        try:
            from prodrag.clients import get_evaluation_chat_model
            from prodrag.config import get_settings
            from prodrag.deepeval_evaluation import (
                OCIChatDeepEvalModel,
                evaluate_deepeval,
            )
        except ImportError as exc:
            parser.error(
                "DeepEval is not installed; run 'uv sync --group dev' before using "
                f"--deepeval ({exc})"
            )
        settings = get_settings()
        judge = OCIChatDeepEvalModel(
            get_evaluation_chat_model(),
            model_name=settings.oci_chat_model,
            retry_attempts=settings.model_retry_attempts,
        )
        metrics.update(evaluate_deepeval(deepeval_records, judge, progress=progress))
    thresholds = {
        "mean_recall": args.min_recall,
        "mean_precision": args.min_precision,
        "hit_rate": args.min_hit_rate,
        "mean_context_precision": args.min_context_precision,
        "mean_context_recall": args.min_context_recall,
    }
    if args.end_to_end:
        thresholds.update(
            {
                "answerability_accuracy": args.min_answerability,
                "citation_document_hit_rate": args.min_citation_hit_rate,
                "abstention_accuracy": args.min_abstention,
                "answer_correctness": args.min_answer_correctness,
                "answer_completeness": args.min_answer_completeness,
                "faithfulness": args.min_faithfulness,
                "citation_correctness": args.min_citation_correctness,
            }
        )
    if args.deepeval:
        thresholds.update(
            {
                "deepeval_contextual_recall": args.min_deepeval_contextual_recall,
                "deepeval_contextual_precision": args.min_deepeval_contextual_precision,
                "deepeval_faithfulness": args.min_deepeval_faithfulness,
                "deepeval_answer_relevancy": args.min_deepeval_answer_relevancy,
            }
        )

    gate_results = _gate_results(metrics, thresholds)
    failed_gates = [name for name, result in gate_results.items() if not result["passed"]]
    passed = not failed_gates
    report = {
        **metrics,
        "metadata": _evaluation_metadata(args.dataset, args.variant),
        "retrieval_case_results": retrieval_case_results,
        "answer_case_results": answer_case_results,
        "gate_results": gate_results,
        "failed_gates": failed_gates,
        "passed": passed,
        "report_only": args.report_only,
    }
    serialized = json.dumps(report, indent=2)
    if not args.no_print_report:
        print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    if args.verbose:
        _print_summary(report, args.output)
    return 0 if passed or args.report_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
