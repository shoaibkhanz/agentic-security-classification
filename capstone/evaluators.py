"""
Capstone-specific evaluators using pydantic-evals.

Wraps the shared evaluators (ClassificationAccuracy, QuestionEfficiency,
EvidenceGrounding, ConfidenceCalibration, ReasoningQuality) into
pydantic-evals Evaluator subclasses so they integrate with the
Dataset.evaluate() pipeline.

Each evaluator's `evaluate` method receives:
  - ctx.output: ClassificationResult (the pipeline's actual output)
  - ctx.inputs: str (the security description)
  - ctx.expected_output: SecurityCategory (what we expect)
  - ctx.metadata: EvalCase (the full eval case with difficulty, notes, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluationReason

from capstone.models import EvalCase
from shared.evaluators import (
    ClassificationAccuracy,
    ConfidenceCalibration,
    EvidenceGrounding,
    QuestionEfficiency,
    ReasoningQuality,
)
from shared.models import ClassificationResult, SecurityCategory


# =============================================================================
# Evaluator 1: Classification Accuracy
# =============================================================================


@dataclass
class ClassificationAccuracyEval(
    Evaluator[str, ClassificationResult, EvalCase],
):
    """
    Score the classification category against the expected category.

    Returns 1.0 for exact match, 0.5 for related categories
    (e.g., SAFE vs convertible_note), 0.0 for wrong.
    """

    def evaluate(
        self,
        ctx: EvaluatorContext[str, ClassificationResult, EvalCase],
    ) -> EvaluationReason:
        expected = ctx.expected_output
        if expected is None:
            return EvaluationReason(value=0.0, reason="No expected output provided")

        # Normalize: expected_output may come in as SecurityCategory or as a string
        if isinstance(expected, SecurityCategory):
            expected_category = expected
        else:
            expected_category = SecurityCategory(str(expected))

        scorer = ClassificationAccuracy()
        score = scorer.score(actual=ctx.output.category, expected=expected_category)

        if score == 1.0:
            reason = f"Correct: {ctx.output.category.value}"
        elif score == 0.5:
            reason = (
                f"Partial: predicted {ctx.output.category.value}, "
                f"expected {expected_category.value} (related category)"
            )
        else:
            reason = (
                f"Wrong: predicted {ctx.output.category.value}, "
                f"expected {expected_category.value}"
            )

        return EvaluationReason(value=score, reason=reason)


# =============================================================================
# Evaluator 2: Efficiency
# =============================================================================


@dataclass
class EfficiencyEval(
    Evaluator[str, ClassificationResult, EvalCase],
):
    """
    Score based on questions_asked relative to the case difficulty.

    Fewer actions for easy cases = better. Hard cases get more slack.
    """

    easy_threshold: int = 3
    medium_threshold: int = 5
    hard_threshold: int = 8

    def evaluate(
        self,
        ctx: EvaluatorContext[str, ClassificationResult, EvalCase],
    ) -> EvaluationReason:
        difficulty = "medium"
        if ctx.metadata is not None:
            difficulty = ctx.metadata.difficulty

        scorer = QuestionEfficiency(
            easy_threshold=self.easy_threshold,
            medium_threshold=self.medium_threshold,
            hard_threshold=self.hard_threshold,
        )
        score = scorer.score(
            questions_asked=ctx.output.questions_asked,
            difficulty=difficulty,
        )

        return EvaluationReason(
            value=score,
            reason=(
                f"Asked {ctx.output.questions_asked} questions "
                f"(difficulty={difficulty}, threshold="
                f"{self._threshold_for(difficulty)})"
            ),
        )

    def _threshold_for(self, difficulty: str) -> int:
        if difficulty == "easy":
            return self.easy_threshold
        if difficulty == "hard":
            return self.hard_threshold
        return self.medium_threshold


# =============================================================================
# Evaluator 3: Evidence Grounding
# =============================================================================


@dataclass
class GroundingEval(
    Evaluator[str, ClassificationResult, EvalCase],
):
    """
    Check that each reasoning step cites specific evidence.

    An ungrounded classification is a hallucination risk.
    Returns the fraction of reasoning steps that have both
    evidence and a source citation.
    """

    def evaluate(
        self,
        ctx: EvaluatorContext[str, ClassificationResult, EvalCase],
    ) -> EvaluationReason:
        scorer = EvidenceGrounding()
        score = scorer.score(ctx.output)

        total_steps = len(ctx.output.reasoning)
        grounded_steps = sum(
            1 for step in ctx.output.reasoning if step.source and step.evidence
        )

        return EvaluationReason(
            value=score,
            reason=f"{grounded_steps}/{total_steps} reasoning steps are grounded",
        )


# =============================================================================
# Evaluator 4: Confidence Calibration
# =============================================================================


@dataclass
class CalibrationEval(
    Evaluator[str, ClassificationResult, EvalCase],
):
    """
    Check if confidence aligns with actual accuracy.

    High confidence on correct answers = well calibrated.
    High confidence on wrong answers = overconfident.
    Low confidence on hard cases = honest (good).
    """

    def evaluate(
        self,
        ctx: EvaluatorContext[str, ClassificationResult, EvalCase],
    ) -> EvaluationReason:
        expected = ctx.expected_output
        if expected is None:
            return EvaluationReason(value=0.0, reason="No expected output provided")

        if isinstance(expected, SecurityCategory):
            expected_category = expected
        else:
            expected_category = SecurityCategory(str(expected))

        is_correct = ctx.output.category == expected_category

        scorer = ConfidenceCalibration()
        score = scorer.score(
            confidence=ctx.output.confidence,
            is_correct=is_correct,
        )

        if is_correct:
            reason = (
                f"Correct with {ctx.output.confidence:.0%} confidence "
                f"(calibration={score:.2f})"
            )
        else:
            reason = (
                f"Wrong with {ctx.output.confidence:.0%} confidence "
                f"(calibration={score:.2f}, lower confidence would be better)"
            )

        return EvaluationReason(value=score, reason=reason)


# =============================================================================
# Evaluator 5: Overall Quality (composite)
# =============================================================================


@dataclass
class OverallQualityEval(
    Evaluator[str, ClassificationResult, EvalCase],
):
    """
    Composite evaluator combining multiple quality dimensions.

    Returns a dict of named scores:
      - accuracy: category correctness (weight: 0.35)
      - efficiency: questions vs difficulty (weight: 0.15)
      - grounding: evidence citation (weight: 0.20)
      - calibration: confidence alignment (weight: 0.15)
      - reasoning_completeness: step quality (weight: 0.15)
      - overall: weighted combination of all metrics

    Weights reflect production priorities: accuracy is most
    important, followed by grounding (hallucination prevention).
    """

    accuracy_weight: float = 0.35
    grounding_weight: float = 0.20
    efficiency_weight: float = 0.15
    calibration_weight: float = 0.15
    reasoning_weight: float = 0.15

    def evaluate(
        self,
        ctx: EvaluatorContext[str, ClassificationResult, EvalCase],
    ) -> dict[str, EvaluationReason]:
        expected = ctx.expected_output
        if expected is None:
            return {
                "overall": EvaluationReason(
                    value=0.0, reason="No expected output provided"
                ),
            }

        if isinstance(expected, SecurityCategory):
            expected_category = expected
        else:
            expected_category = SecurityCategory(str(expected))

        # Accuracy
        accuracy_scorer = ClassificationAccuracy()
        accuracy_score = accuracy_scorer.score(
            actual=ctx.output.category,
            expected=expected_category,
        )

        # Efficiency
        difficulty = "medium"
        if ctx.metadata is not None:
            difficulty = ctx.metadata.difficulty
        efficiency_scorer = QuestionEfficiency()
        efficiency_score = efficiency_scorer.score(
            questions_asked=ctx.output.questions_asked,
            difficulty=difficulty,
        )

        # Grounding
        grounding_scorer = EvidenceGrounding()
        grounding_score = grounding_scorer.score(ctx.output)

        # Calibration
        is_correct = ctx.output.category == expected_category
        calibration_scorer = ConfidenceCalibration()
        calibration_score = calibration_scorer.score(
            confidence=ctx.output.confidence,
            is_correct=is_correct,
        )

        # Reasoning
        reasoning_scorer = ReasoningQuality()
        reasoning_scores = reasoning_scorer.score(ctx.output)
        reasoning_score = reasoning_scores["step_completeness"]

        # Weighted overall
        overall = (
            self.accuracy_weight * accuracy_score
            + self.efficiency_weight * efficiency_score
            + self.grounding_weight * grounding_score
            + self.calibration_weight * calibration_score
            + self.reasoning_weight * reasoning_score
        )

        return {
            "accuracy": EvaluationReason(
                value=accuracy_score,
                reason=f"{ctx.output.category.value} vs {expected_category.value}",
            ),
            "efficiency": EvaluationReason(
                value=efficiency_score,
                reason=f"{ctx.output.questions_asked} questions ({difficulty})",
            ),
            "grounding": EvaluationReason(
                value=grounding_score,
                reason=f"{len(ctx.output.reasoning)} reasoning steps",
            ),
            "calibration": EvaluationReason(
                value=calibration_score,
                reason=f"confidence={ctx.output.confidence:.0%}, correct={is_correct}",
            ),
            "reasoning_completeness": EvaluationReason(
                value=reasoning_score,
                reason="completeness of reasoning chain",
            ),
            "overall": EvaluationReason(
                value=round(overall, 3),
                reason=(
                    f"Weighted: acc={accuracy_score:.2f} eff={efficiency_score:.2f} "
                    f"gnd={grounding_score:.2f} cal={calibration_score:.2f} "
                    f"rsn={reasoning_score:.2f}"
                ),
            ),
        }
