from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from prodrag.container import get_retrieval_service


class EvaluationCase(BaseModel):
    question: str
    expected_document_ids: list[str] = Field(default_factory=list)
    expected_answerable: bool = True
    tenant_id: str = "default"
    product: str | None = None
    version: str | None = None

    @model_validator(mode="after")
    def validate_labels(self):
        if self.expected_answerable and not self.expected_document_ids:
            raise ValueError("Answerable rows require expected_document_ids")
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


def evaluate(cases: list[EvaluationCase]) -> dict[str, float | int]:
    service = get_retrieval_service()
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    hits = 0
    unanswerable_count = 0
    correct_abstentions = 0
    for case in cases:
        results = service.retrieve(
            case.question,
            tenant_id=case.tenant_id,
            product=case.product,
            version=case.version,
        )
        ranked_ids = [str(item.document.metadata.get("document_id")) for item in results]
        if not case.expected_answerable:
            unanswerable_count += 1
            correct_abstentions += int(not ranked_ids)
            continue
        expected = set(case.expected_document_ids)
        found = expected.intersection(ranked_ids)
        recalls.append(len(found) / len(expected))
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
    count = len(recalls)
    return {
        "questions": len(cases),
        "answerable_questions": count,
        "unanswerable_questions": unanswerable_count,
        "hit_rate": hits / count if count else 1.0,
        "mean_recall": sum(recalls) / count if count else 1.0,
        "mrr": sum(reciprocal_ranks) / count if count else 1.0,
        "abstention_accuracy": (
            correct_abstentions / unanswerable_count if unanswerable_count else 1.0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate prodRAG retrieval against JSONL labels")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--min-recall", type=float, default=0.95)
    parser.add_argument("--min-hit-rate", type=float, default=0.95)
    parser.add_argument("--min-abstention", type=float, default=0.90)
    args = parser.parse_args()
    metrics = evaluate(load_cases(args.dataset))
    print(json.dumps(metrics, indent=2))
    passed = (
        metrics["mean_recall"] >= args.min_recall
        and metrics["hit_rate"] >= args.min_hit_rate
        and metrics["abstention_accuracy"] >= args.min_abstention
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
