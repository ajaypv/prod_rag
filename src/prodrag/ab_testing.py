from __future__ import annotations

import argparse
import json
import math
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    baseline: float | None = None
    candidate: float | None = None
    limit: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "baseline": self.baseline,
            "candidate": self.candidate,
            "limit": self.limit,
        }


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Evaluation report must be a JSON object: {path}")
    return payload


def load_policy(path: Path) -> dict[str, dict[str, float]]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    policy: dict[str, dict[str, float]] = {}
    for section in ("absolute", "max_regression", "max_relative_increase"):
        raw = payload.get(section, {})
        if not isinstance(raw, dict):
            raise ValueError(f"Policy section [{section}] must be a table")
        values: dict[str, float] = {}
        for name, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"Policy value {section}.{name} must be numeric")
            numeric = float(value)
            if not math.isfinite(numeric) or numeric < 0:
                raise ValueError(f"Policy value {section}.{name} must be finite and non-negative")
            values[name] = numeric
        policy[section] = values
    if not any(policy.values()):
        raise ValueError("A/B policy does not contain any checks")
    return policy


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, dict[str, float]],
) -> dict[str, object]:
    checks: list[CheckResult] = []
    checks.extend(_compatibility_checks(baseline, candidate))

    if candidate.get("passed") is False:
        failed = candidate.get("failed_gates", [])
        checks.append(
            CheckResult(
                name="candidate_internal_gates",
                passed=False,
                detail=f"Candidate failed its configured gates: {failed}",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="candidate_internal_gates",
                passed=True,
                detail="Candidate passed its configured absolute gates",
            )
        )

    for metric, minimum in policy["absolute"].items():
        candidate_value = _metric(candidate, metric)
        checks.append(
            CheckResult(
                name=f"absolute.{metric}",
                passed=candidate_value is not None and candidate_value >= minimum,
                detail=(
                    f"Candidate {metric}={candidate_value!r}; required minimum={minimum}"
                ),
                candidate=candidate_value,
                limit=minimum,
            )
        )

    for metric, maximum_drop in policy["max_regression"].items():
        baseline_value = _metric(baseline, metric)
        candidate_value = _metric(candidate, metric)
        lower_bound = (
            baseline_value - maximum_drop if baseline_value is not None else None
        )
        checks.append(
            CheckResult(
                name=f"max_regression.{metric}",
                passed=(
                    baseline_value is not None
                    and candidate_value is not None
                    and candidate_value >= baseline_value - maximum_drop
                ),
                detail=(
                    f"Baseline={baseline_value!r}, candidate={candidate_value!r}, "
                    f"maximum allowed drop={maximum_drop}"
                ),
                baseline=baseline_value,
                candidate=candidate_value,
                limit=lower_bound,
            )
        )

    for metric, maximum_increase in policy["max_relative_increase"].items():
        baseline_value = _metric(baseline, metric)
        candidate_value = _metric(candidate, metric)
        upper_bound = (
            baseline_value * (1 + maximum_increase)
            if baseline_value is not None
            else None
        )
        checks.append(
            CheckResult(
                name=f"max_relative_increase.{metric}",
                passed=(
                    baseline_value is not None
                    and candidate_value is not None
                    and upper_bound is not None
                    and candidate_value <= upper_bound
                ),
                detail=(
                    f"Baseline={baseline_value!r}, candidate={candidate_value!r}, "
                    f"maximum relative increase={maximum_increase}"
                ),
                baseline=baseline_value,
                candidate=candidate_value,
                limit=upper_bound,
            )
        )

    failed = [check.name for check in checks if not check.passed]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline": _report_identity(baseline),
        "candidate": _report_identity(candidate),
        "checks": [check.as_dict() for check in checks],
        "failed_checks": failed,
        "passed": not failed,
    }


def write_junit(report: dict[str, object], path: Path) -> None:
    checks = report.get("checks", [])
    if not isinstance(checks, list):
        raise ValueError("Comparison report checks must be a list")
    failures = sum(
        1 for check in checks if isinstance(check, dict) and not check.get("passed", False)
    )
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": "prodRAG A/B evaluation gate",
            "tests": str(len(checks)),
            "failures": str(failures),
            "errors": "0",
        },
    )
    for check in checks:
        if not isinstance(check, dict):
            continue
        case = ElementTree.SubElement(
            suite,
            "testcase",
            {"classname": "prodrag.ab", "name": str(check.get("name", "unknown"))},
        )
        detail = str(check.get("detail", ""))
        if not check.get("passed", False):
            failure = ElementTree.SubElement(case, "failure", {"message": detail})
            failure.text = detail
        output = ElementTree.SubElement(case, "system-out")
        output.text = detail
    path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _compatibility_checks(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> list[CheckResult]:
    baseline_metadata = baseline.get("metadata", {})
    candidate_metadata = candidate.get("metadata", {})
    if not isinstance(baseline_metadata, dict) or not isinstance(candidate_metadata, dict):
        return [
            CheckResult(
                name="compatible.metadata",
                passed=False,
                detail="Both reports must contain metadata objects",
            )
        ]

    checks: list[CheckResult] = []
    for key in ("dataset_sha256", "corpus_manifest_sha256"):
        baseline_value = baseline_metadata.get(key)
        candidate_value = candidate_metadata.get(key)
        checks.append(
            CheckResult(
                name=f"compatible.{key}",
                passed=(
                    isinstance(baseline_value, str)
                    and bool(baseline_value)
                    and baseline_value == candidate_value
                ),
                detail=(
                    f"Baseline {key}={baseline_value!r}; candidate {key}={candidate_value!r}"
                ),
            )
        )
    return checks


def _metric(report: dict[str, Any], name: str) -> float | None:
    value = report.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _report_identity(report: dict[str, Any]) -> dict[str, object]:
    metadata = report.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "variant": metadata.get("variant"),
        "git_sha": metadata.get("git_sha"),
        "dataset_sha256": metadata.get("dataset_sha256"),
        "corpus_manifest_sha256": metadata.get("corpus_manifest_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare prodRAG baseline and candidate evaluation reports"
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junit-output", type=Path)
    args = parser.parse_args()

    report = compare_reports(
        load_report(args.baseline),
        load_report(args.candidate),
        load_policy(args.policy),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.junit_output:
        write_junit(report, args.junit_output)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
