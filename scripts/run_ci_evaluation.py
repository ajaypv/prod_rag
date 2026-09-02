from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

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


def _run_ingestion(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    source: Path,
    index: int,
    total: int,
) -> int:
    print(f"\n[Ingest {index}/{total}] {source.name}", flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.stderr.strip():
        print(completed.stderr.rstrip(), file=sys.stderr, flush=True)
    if completed.returncode != 0:
        if completed.stdout.strip():
            print(completed.stdout.rstrip(), flush=True)
        print("  Status: FAILED", flush=True)
        return completed.returncode

    payload: dict[str, object] | None = None
    for line in reversed(completed.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        print("  Status: completed, but no ingestion summary was returned", flush=True)
    else:
        print(f"  Document ID: {payload.get('document_id', source.stem)}", flush=True)
        print(f"  Parent sections: {payload.get('parents_indexed', 'n/a')}", flush=True)
        print(f"  Search chunks: {payload.get('chunks_indexed', 'n/a')}", flush=True)
        print("  Status: READY", flush=True)
    return 0


def _wait_for_qdrant(base_url: str, timeout_seconds: float = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    readiness_url = f"{base_url.rstrip('/')}/readyz"
    while time.monotonic() < deadline:
        try:
            with urlopen(readiness_url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return
        except (OSError, URLError):
            time.sleep(1)
    raise TimeoutError(f"Qdrant did not become ready within {timeout_seconds}s: {readiness_url}")


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
    parser.add_argument(
        "--reuse-data-dir",
        action="store_true",
        help=(
            "Skip corpus ingestion and reuse an existing non-empty local data directory; "
            "intended only to resume a failed local evaluation"
        ),
    )
    args = parser.parse_args()

    dataset = args.dataset.resolve(strict=True)
    manifest_path = args.manifest.resolve(strict=True)
    policy_path = args.policy.resolve(strict=True)
    data_dir = args.data_dir.resolve()
    has_existing_data = data_dir.exists() and any(data_dir.iterdir())
    if has_existing_data and not args.reuse_data_dir:
        raise RuntimeError(
            f"CI data directory must be empty: {data_dir}. Use a new --data-dir, "
            "or add --reuse-data-dir to resume evaluation with this existing local index."
        )
    if args.reuse_data_dir and not has_existing_data:
        parser.error("--reuse-data-dir requires an existing non-empty --data-dir")
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
    if args.qdrant_url:
        _wait_for_qdrant(args.qdrant_url)

    print("=" * 72, flush=True)
    print(f"Preparing prodRAG evaluation variant: {args.variant}", flush=True)
    print("=" * 72, flush=True)
    print(f"Dataset: {dataset}", flush=True)
    print(f"Corpus manifest: {manifest_path}", flush=True)
    print(f"Corpus files: {len(files)}", flush=True)
    print(f"Data directory: {data_dir}", flush=True)
    print(f"Qdrant: {args.qdrant_url or data_dir / 'qdrant'}", flush=True)
    print(
        f"Index mode: {'REUSE EXISTING (ingestion skipped)' if args.reuse_data_dir else 'REBUILD'}",
        flush=True,
    )

    tenant = str(manifest.get("tenant_id", "default"))
    product = manifest.get("product")
    version = manifest.get("version")
    if args.reuse_data_dir:
        print("\nExisting index selected; skipping all corpus ingestion steps.", flush=True)
    else:
        for index, source in enumerate(files, start=1):
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
            if (
                _run_ingestion(
                    command,
                    cwd=project_root,
                    environment=environment,
                    source=source,
                    index=index,
                    total=len(files),
                )
                != 0
            ):
                return 2

    print("\n" + "=" * 72, flush=True)
    print("Corpus ready. Starting retrieval, answer, and DeepEval checks.", flush=True)
    print("=" * 72, flush=True)
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
        "--report-only",
        "--verbose",
        "--no-print-report",
    ]
    for metric, threshold in thresholds.items():
        command.extend((_THRESHOLD_FLAGS[metric], str(threshold)))
    return _run(command, cwd=project_root, environment=environment)


if __name__ == "__main__":
    raise SystemExit(main())
