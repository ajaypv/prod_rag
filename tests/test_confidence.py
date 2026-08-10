from langchain_core.documents import Document

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import ConfidenceLevel
from prodrag.retrieval.confidence import ScoreThresholdConfidenceGrader


def test_confidence_grader_uses_configured_rerank_thresholds() -> None:
    grader = ScoreThresholdConfidenceGrader(Settings(_env_file=None))

    def candidate(score: float) -> RetrievedCandidate:
        return RetrievedCandidate(Document(page_content="context"), 0.1, score)

    assert grader.grade([candidate(0.9)]) == ConfidenceLevel.HIGH
    assert grader.grade([candidate(0.5)]) == ConfidenceLevel.MEDIUM
    assert grader.grade([candidate(0.2)]) == ConfidenceLevel.LOW
    assert grader.grade([]) == ConfidenceLevel.LOW
