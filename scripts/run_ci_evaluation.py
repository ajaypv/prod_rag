from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


_THRESHOLD_FLAGS = {
    "mean_recall": "--min-recall",
    "mean_precision": "--min-precision",
    "hit_rate": "--min-hit-rate",
    "mean_context_precision": "--min-context-precision",
    "mean_context_recall": "--min-context-recall",
    "answerability_accuracy": "--min-answerability",
    "citation_document_hit_rate": "--min-citation-hit-rate",
    "abstention_accuracy": "--min-abstention",
    "answer_correctness": "--min-answer-correctness",
    "answer_completeness": "--min-answer-completeness",
    "faithfulness": "--min-faithfulness",
    "citation_correctness": "--min-citation-correctness",
    "deepeval_contextual_recall": "--min-deepeval-contextual-recall",
    "deepeval_contextual_precision": "--min-deepeval-contextual-precision",
    "deepeval_faithfulness": "--min-deepeval-faithfulness",
    "deepeval_answer_relevancy": "--min-deepeval-answer-relevancy",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path, project_root: Path) -> tuple[dict[str, Any], list[Path]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ValueError("Corpus manifest must be an object containing a files list")

    files: list[Path] = []
    for index, entry in enumerate(payload["files"], start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Corpus manifest entry {index} must be an object")
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ValueError(f"Corpus manifest entry {index} requires path and sha256")
        source = (project_root / relative).resolve(strict=True)
        if not source.is_relative_to(project_root):
            raise ValueError(f"Corpus path escapes the project root: {relative}")
        actual_hash = _sha256(source)
        if actual_hash != expected_hash.lower():
            raise ValueError(
                f"Corpus checksum mismatch for {relative}: expected {expected_hash}, "
                f"got {actual_hash}"
            )
        files.append(source)
    if not files:
        raise ValueError("Corpus manifest cannot be empty")
    return payload, files


def _load_absolute_thresholds(path: Path) -> dict[str, float]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    absolute = payload.get("absolute")
    if not isinstance(absolute, dict):
        raise ValueError("Gate policy must contain an [absolute] table")
    thresholds: dict[str, float] = {}
    for metric, value in absolute.items():
        if metric not in _THRESHOLD_FLAGS:
            raise ValueError(f"Unsupported absolute gate metric: {metric}")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"Absolute gate {metric} must be numeric")
        thresholds[metric] = float(value)
    return thresholds


def _base_environment(
    *,
    data_dir: Path,
    manifest_path: Path,
    variant: str,
    git_sha: str,
    qdrant_url: str | None,
) -> dict[str, str]:
    if os.getenv("CONFIDENT_API_KEY"):
        raise RuntimeError(
            "CONFIDENT_API_KEY must be unset: CI evaluation is local-only and must not upload"
        )
    environment = os.environ.copy()
    environment.update(
        {
            "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
            "DEEPEVAL_DISABLE_DOTENV": "1",
            "DEEPEVAL_DISABLE_LEGACY_KEYFILE": "1",
            "DEEPEVAL_NO_INSPECT_PROMPT": "1",
            "RAG_ENVIRONMENT": "test",
            "RAG_DATA_DIR": str(data_dir),
            "RAG_PARENT_STORE_PATH": str(data_dir / "parents.sqlite3"),
            "QDRANT_COLLECTION": f"prodrag_ci_{variant}",
            "PRODRAG_EVAL_VARIANT": variant,
            "PRODRAG_EVAL_GIT_SHA": git_sha,
            "PRODRAG_CORPUS_MANIFEST_SHA256": _sha256(manifest_path),
        }
    )
    environment.pop("CONFIDENT_API_KEY", None)
    if qdrant_url:
        environment["QDRANT_URL"] = qdrant_url
        environment["QDRANT_PATH"] = ""
        environment["QDRANT_HNSW_ENABLED"] = "true"
    else:
        environment["QDRANT_PATH"] = str(data_dir / "qdrant")
        environment["QDRANT_HNSW_ENABLED"] = "false"
    return environment


def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> int:
    completed = subprocess.run(command, cwd=cwd, env=environment, check=False)
    return completed.returncode


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Rebuild an isolated prodRAG index and run the local CI evaluation"
    )
    parser.add_argument("--variant", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--git-sha", default=os.getenv("CI_COMMIT_SHA", "unknown"))
    parser.add_argument(
        "--dataset",
        type=Path,
        default=project_root / "eval" / "b2b-saas-ci.jsonl",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project_root / "eval" / "corpus-manifest.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=project_root / "eval" / "gates.toml",
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qdrant-url")
    args = parser.parse_args()

    dataset = args.dataset.resolve(strict=True)
    manifest_path = args.manifest.resolve(strict=True)
    policy_path = args.policy.resolve(strict=True)
    data_dir = args.data_dir.resolve()
    if data_dir.exists() and any(data_dir.iterdir()):
        raise RuntimeError(f"CI data directory must be empty: {data_dir}")
    data_dir.mkdir(parents=True, exist_ok=True)

    manifest, files = _load_manifest(manifest_path, project_root)
    thresholds = _load_absolute_thresholds(policy_path)
    environment = _base_environment(
        data_dir=data_dir,
        manifest_path=manifest_path,
        variant=args.variant,
        git_sha=args.git_sha,
        qdrant_url=args.qdrant_url,
    )

    tenant = str(manifest.get("tenant_id", "default"))
    product = manifest.get("product")
    version = manifest.get("version")
    for source in files:
        command = [
            sys.executable,
            "-m",
            "prodrag.cli",
            "ingest",
            str(source),
            "--tenant",
            tenant,
        ]
        if product:
            command.extend(("--product", str(product)))
        if version:
            command.extend(("--version", str(version)))
        if _run(command, cwd=project_root, environment=environment) != 0:
            return 2

    command = [
        sys.executable,
        "-m",
        "prodrag.evaluation",
        str(dataset),
        "--end-to-end",
        "--deepeval",
        "--variant",
        args.variant,
        "--output",
        str(args.output.resolve()),
    ]
    for metric, threshold in thresholds.items():
        command.extend((_THRESHOLD_FLAGS[metric], str(threshold)))
    return _run(command, cwd=project_root, environment=environment)


if __name__ == "__main__":
    raise SystemExit(main())
