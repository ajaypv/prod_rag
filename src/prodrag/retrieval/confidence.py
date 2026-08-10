from collections.abc import Sequence
from typing import Protocol

from prodrag.config import Settings
from prodrag.domain import RetrievedCandidate
from prodrag.models import ConfidenceLevel


class ConfidenceGrader(Protocol):
    def grade(self, candidates: Sequence[RetrievedCandidate]) -> ConfidenceLevel: ...


class ScoreThresholdConfidenceGrader:
    """Map the strongest final retrieval score to a configured confidence level."""

    def __init__(self, settings: Settings) -> None:
        self.medium_threshold = settings.confidence_medium_threshold
        self.high_threshold = settings.confidence_high_threshold

    def grade(self, candidates: Sequence[RetrievedCandidate]) -> ConfidenceLevel:
        if not candidates:
            return ConfidenceLevel.LOW

        top_score = max(candidate.final_score for candidate in candidates)
        if top_score >= self.high_threshold:
            return ConfidenceLevel.HIGH
        if top_score >= self.medium_threshold:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
