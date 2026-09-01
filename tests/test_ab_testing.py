from xml.etree import ElementTree

from prodrag.ab_testing import compare_reports, write_junit


def _report(*, variant: str, recall: float, latency: float, passed: bool = True):
    return {
        "metadata": {
            "variant": variant,
            "git_sha": f"sha-{variant}",
            "dataset_sha256": "dataset-sha",
            "corpus_manifest_sha256": "corpus-sha",
        },
        "mean_recall": recall,
        "deepeval_faithfulness": 0.92,
        "end_to_end_p95_ms": latency,
        "passed": passed,
        "failed_gates": [] if passed else ["mean_recall"],
    }


def _policy():
    return {
        "absolute": {"mean_recall": 0.9, "deepeval_faithfulness": 0.9},
        "max_regression": {"mean_recall": 0.02},
        "max_relative_increase": {"end_to_end_p95_ms": 0.1},
    }


def test_compare_reports_passes_compatible_candidate() -> None:
    report = compare_reports(
        _report(variant="baseline", recall=0.96, latency=1000),
        _report(variant="candidate", recall=0.95, latency=1080),
        _policy(),
    )

    assert report["passed"] is True
    assert report["failed_checks"] == []


def test_compare_reports_fails_quality_and_latency_regressions() -> None:
    report = compare_reports(
        _report(variant="baseline", recall=0.96, latency=1000),
        _report(variant="candidate", recall=0.89, latency=1200, passed=False),
        _policy(),
    )

    assert report["passed"] is False
    assert "candidate_internal_gates" in report["failed_checks"]
    assert "absolute.mean_recall" in report["failed_checks"]
    assert "max_regression.mean_recall" in report["failed_checks"]
    assert "max_relative_increase.end_to_end_p95_ms" in report["failed_checks"]


def test_compare_reports_rejects_different_dataset() -> None:
    baseline = _report(variant="baseline", recall=0.96, latency=1000)
    candidate = _report(variant="candidate", recall=0.96, latency=1000)
    candidate["metadata"]["dataset_sha256"] = "different"

    report = compare_reports(baseline, candidate, _policy())

    assert "compatible.dataset_sha256" in report["failed_checks"]


def test_write_junit_records_failed_checks(tmp_path) -> None:
    report = compare_reports(
        _report(variant="baseline", recall=0.96, latency=1000),
        _report(variant="candidate", recall=0.89, latency=1000),
        _policy(),
    )
    output = tmp_path / "comparison.xml"

    write_junit(report, output)

    suite = ElementTree.parse(output).getroot()
    assert suite.attrib["name"] == "prodRAG A/B evaluation gate"
    assert int(suite.attrib["failures"]) >= 1
