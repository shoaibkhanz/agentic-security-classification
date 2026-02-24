"""
Reusable evaluators for the tutorial curriculum.

These evaluators are used across modules 09-10 and the capstone
to assess agent quality. They follow pydantic-evals patterns.

Eval philosophy (Hamel Husain / Shreya Shankar):
  - Build evaluators from errors you DISCOVER, not errors you IMAGINE
  - Validate that automated judges agree with human judgment
  - Measure quality distributions, not binary pass/fail
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.models import ClassificationResult, SecurityCategory


@dataclass
class ClassificationAccuracy:
    """
    Check if the classification category matches expected.

    Returns 1.0 for exact match, 0.5 for related category, 0.0 for wrong.
    """

    # Related categories that get partial credit
    RELATED_CATEGORIES: dict[SecurityCategory, set[SecurityCategory]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.RELATED_CATEGORIES is None:
            self.RELATED_CATEGORIES = {
                SecurityCategory.CONVERTIBLE_NOTE: {
                    SecurityCategory.DEBT,
                    SecurityCategory.SAFE,
                },
                SecurityCategory.SAFE: {
                    SecurityCategory.CONVERTIBLE_NOTE,
                    SecurityCategory.EQUITY,
                },
                SecurityCategory.FUND_INTEREST: {
                    SecurityCategory.REAL_ESTATE,
                    SecurityCategory.EQUITY,
                },
                SecurityCategory.REAL_ESTATE: {
                    SecurityCategory.FUND_INTEREST,
                },
            }

    def score(
        self,
        actual: SecurityCategory,
        expected: SecurityCategory,
    ) -> float:
        """Score the classification accuracy."""
        if actual == expected:
            return 1.0
        related = self.RELATED_CATEGORIES.get(expected, set())
        if actual in related:
            return 0.5
        return 0.0


@dataclass
class QuestionEfficiency:
    """
    Evaluate how many questions/actions were needed to classify.

    Fewer actions = better (agent is efficient at gathering information).
    Score based on expected range for the difficulty level.
    """

    easy_threshold: int = 3
    medium_threshold: int = 5
    hard_threshold: int = 8

    def score(self, questions_asked: int, difficulty: str = "medium") -> float:
        """Score based on number of questions for the difficulty level."""
        if difficulty == "easy":
            threshold = self.easy_threshold
        elif difficulty == "hard":
            threshold = self.hard_threshold
        else:
            threshold = self.medium_threshold

        if questions_asked <= threshold:
            return 1.0
        elif questions_asked <= threshold * 1.5:
            return 0.5
        return 0.0


@dataclass
class EvidenceGrounding:
    """
    Check if the classification reasoning cites specific evidence.

    An ungrounded classification that doesn't reference tool results
    is a hallucination risk. Every reasoning step should cite a source.
    """

    def score(self, result: ClassificationResult) -> float:
        """Score based on evidence grounding."""
        if not result.reasoning:
            return 0.0

        grounded_steps = sum(
            1 for step in result.reasoning if step.source and step.evidence
        )
        return grounded_steps / len(result.reasoning)


@dataclass
class ConfidenceCalibration:
    """
    Check if confidence scores align with actual accuracy.

    High confidence on correct answers = good calibration.
    High confidence on wrong answers = bad calibration.
    Low confidence on hard cases = honest uncertainty (good).
    """

    def score(
        self,
        confidence: float,
        is_correct: bool,
    ) -> float:
        """
        Score confidence calibration.

        Returns high score when:
        - High confidence + correct = well calibrated
        - Low confidence + wrong = honest uncertainty
        Returns low score when:
        - High confidence + wrong = overconfident
        - Low confidence + correct = underconfident
        """
        if is_correct:
            # Correct answer: reward higher confidence
            return confidence
        else:
            # Wrong answer: reward lower confidence (honest uncertainty)
            return 1.0 - confidence


@dataclass
class ReasoningQuality:
    """
    Evaluate if reasoning steps logically connect evidence to inference.

    Checks:
    - Steps are ordered (step numbers increase)
    - Each step has both evidence and inference
    - Confidence deltas are reasonable
    - The chain logically leads to the conclusion
    """

    def score(self, result: ClassificationResult) -> dict[str, float]:
        """Score multiple aspects of reasoning quality."""
        if not result.reasoning:
            return {
                "has_reasoning": 0.0,
                "step_completeness": 0.0,
                "confidence_progression": 0.0,
            }

        # Check step completeness
        complete_steps = sum(
            1
            for step in result.reasoning
            if step.evidence and step.inference and step.source
        )
        completeness = complete_steps / len(result.reasoning)

        # Check confidence progression (deltas should make sense)
        positive_deltas = sum(
            1 for step in result.reasoning if step.confidence_delta > 0
        )
        progression = positive_deltas / len(result.reasoning)

        return {
            "has_reasoning": 1.0,
            "step_completeness": completeness,
            "confidence_progression": progression,
        }
