import hashlib
import json
from pathlib import Path

from prodrag.evaluation import load_cases
from prodrag.ingestion.parsing import DoclingParser, MarkdownSectioner
from prodrag.models import TicketCategory

PROJECT_ROOT = Path(__file__).parents[1]
SAMPLE_ROOT = PROJECT_ROOT / "samples" / "b2b-saas"


def test_demo_documents_parse_and_match_evaluation_ids() -> None:
    sources = sorted(
        path for path in SAMPLE_ROOT.iterdir() if path.suffix.lower() in {".md", ".html"}
    )
    assert len(sources) == 9
    assert any(source.suffix.lower() == ".html" for source in sources)

    parser = DoclingParser(max_file_bytes=1_000_000)
    sectioner = MarkdownSectioner(max_parent_chars=2_000)
    document_ids = {source.stem for source in sources}
    for source in sources:
        parsed = parser.parse(source)
        sections = sectioner.split(parsed.markdown, default_heading=parsed.title)
        assert parsed.title.startswith("NimbusFlow")
        assert sections
        if source.suffix.lower() == ".html":
            assert parsed.metadata["extension"] == ".html"
            assert "HTTP 429" in parsed.markdown
            assert any("API limits" in section.heading for section in sections)

    cases = load_cases(PROJECT_ROOT / "eval" / "b2b-saas.jsonl")
    expected_ids = {
        document_id
        for case in cases
        for document_id in case.expected_document_ids
    }
    assert expected_ids <= document_ids


def test_demo_query_expectations_use_public_response_categories() -> None:
    query_file = PROJECT_ROOT / "samples" / "b2b-saas-demo-queries.jsonl"
    cases = [json.loads(line) for line in query_file.read_text().splitlines() if line]

    assert len(cases) == 6
    assert {case["expected_category"] for case in cases} <= {
        category.value for category in TicketCategory
    }
    assert any(case["expected_human_review"] for case in cases)
    assert any(not case["expected_human_review"] for case in cases)


def test_ci_corpus_manifest_and_goldens_are_reproducible() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "eval" / "corpus-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["tenant_id"] == "demo"
    assert len(manifest["files"]) == 9
    for entry in manifest["files"]:
        source = (PROJECT_ROOT / entry["path"]).resolve(strict=True)
        assert source.is_relative_to(PROJECT_ROOT)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]

    cases = load_cases(PROJECT_ROOT / "eval" / "b2b-saas-ci.jsonl")
    assert len(cases) == 11
    assert sum(bool(case.expected_answer) for case in cases) == 9
    assert sum(not case.expected_answerable for case in cases) == 2
