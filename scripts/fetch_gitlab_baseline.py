from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download the latest successful prodRAG baseline artifact from GitLab"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--job", default="rag-reference")
    args = parser.parse_args()

    required = ("CI_API_V4_URL", "CI_PROJECT_ID", "CI_JOB_TOKEN")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing GitLab variables: {', '.join(missing)}")
    target_ref = os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME") or os.getenv(
        "CI_DEFAULT_BRANCH"
    )
    if not target_ref:
        raise RuntimeError("GitLab did not provide a target or default branch")

    base_url = os.environ["CI_API_V4_URL"].rstrip("/")
    project = quote(os.environ["CI_PROJECT_ID"], safe="")
    ref = quote(target_ref, safe="")
    artifact_path = quote("artifacts/reference.json", safe="/")
    job = quote(args.job, safe="")
    url = (
        f"{base_url}/projects/{project}/jobs/artifacts/{ref}/raw/{artifact_path}"
        f"?job={job}"
    )
    request = Request(url, headers={"JOB-TOKEN": os.environ["CI_JOB_TOKEN"]})
    with urlopen(request, timeout=60) as response:
        payload = response.read()

    report = json.loads(payload)
    if not isinstance(report, dict) or "metadata" not in report:
        raise ValueError("Downloaded baseline artifact is not a prodRAG evaluation report")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
