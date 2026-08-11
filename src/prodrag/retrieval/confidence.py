from collections.abc import Sequence
from typing import Protocol

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import ConfidenceLevel


class ConfidenceGrader(Protocol):
    """Translate retrieval evidence into the low/medium/high CLI vocabulary."""
    def grade(self, candidates: Sequence[RetrievedCandidate]) -> ConfidenceLevel:
        """Grade the final ordered evidence returned by retrieval."""
        ...


class ScoreThresholdConfidenceGrader:
    """Map the strongest final retrieval score to a configured confidence level.

    With defaults, ``0.82`` is high, ``0.50`` is medium, and ``0.20`` is low. This local
    routing guard is not a probability that the answer is correct. Recalibrate thresholds when
    changing the rerank model or disabling reranking.
    """

    def __init__(self, settings: Settings) -> None:
        self.medium_threshold = settings.confidence_medium_threshold
        self.high_threshold = settings.confidence_high_threshold

    def grade(self, candidates: Sequence[RetrievedCandidate]) -> ConfidenceLevel:
        """Grade from the best result because one strong source can support an answer."""
        if not candidates:
            return ConfidenceLevel.LOW

        top_score = max(candidate.final_score for candidate in candidates)
        if top_score >= self.high_threshold:
            return ConfidenceLevel.HIGH
        if top_score >= self.medium_threshold:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
