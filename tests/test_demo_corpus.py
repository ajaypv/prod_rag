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
