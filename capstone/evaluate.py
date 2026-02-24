"""
Evaluation runner for the private securities classification pipeline.

Run with:
    uv run python -m capstone.evaluate
    uv run python -m capstone.evaluate --cases atlas_senior_notes novatech_safe
    uv run python -m capstone.evaluate --dataset capstone/datasets/cases_v1.yaml

Workflow:
  1. Load eval cases from a YAML dataset file
  2. Run classify_security() for each case
  3. Score results using capstone evaluators
  4. Print a formatted report with per-case and aggregate metrics
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import yaml

from capstone.evaluators import (
    CalibrationEval,
    ClassificationAccuracyEval,
    EfficiencyEval,
    GroundingEval,
    OverallQualityEval,
)
from capstone.graph import classify_security
from capstone.models import EvalCase
from shared.deps import AnalystContext
from shared.models import ClassificationResult, SecurityCategory


# =============================================================================
# Dataset Loading
# =============================================================================


def load_eval_cases(dataset_path: Path) -> list[EvalCase]:
    """Load evaluation cases from a YAML file."""
    raw = yaml.safe_load(dataset_path.read_text())
    cases: list[EvalCase] = []

    for raw_case in raw.get("cases", []):
        case = EvalCase(
            name=raw_case["name"],
            security_description=raw_case["security_description"].strip(),
            expected_category=SecurityCategory(raw_case["expected_category"]),
            difficulty=raw_case.get("difficulty", "medium"),
            expected_max_questions=raw_case.get("expected_max_questions", 5),
            notes=raw_case.get("notes", "").strip(),
        )
        cases.append(case)

    return cases


def filter_cases(
    cases: list[EvalCase],
    names: list[str] | None,
) -> list[EvalCase]:
    """Filter cases by name. Returns all cases if names is None."""
    if names is None:
        return cases

    name_set = set(names)
    filtered = [c for c in cases if c.name in name_set]

    missing = name_set - {c.name for c in filtered}
    if missing:
        available = [c.name for c in cases]
        print(f"WARNING: Cases not found: {sorted(missing)}")
        print(f"  Available: {available}")

    return filtered


# =============================================================================
# Single Case Evaluation
# =============================================================================


async def evaluate_single_case(
    case: EvalCase,
    deps: AnalystContext,
) -> tuple[ClassificationResult, dict[str, float], float]:
    """
    Run the classification pipeline on a single eval case and score it.

    Returns:
        (classification_result, scores_dict, duration_seconds)
    """
    start_time = time.perf_counter()

    result, state = await classify_security(
        description=case.security_description,
        deps=deps,
        confidence_threshold=0.82,
        max_actions=case.expected_max_questions + 3,  # Allow some slack beyond expected
    )

    duration = time.perf_counter() - start_time

    # Build a minimal evaluator context to score manually
    # (We score directly rather than through pydantic-evals Dataset.evaluate
    #  because our task signature doesn't match the simple InputsT -> OutputT pattern)
    from pydantic_evals.evaluators.context import EvaluatorContext
    from pydantic_evals.otel._errors import SpanTreeRecordingError

    ctx = EvaluatorContext(
        name=case.name,
        inputs=case.security_description,
        metadata=case,
        expected_output=case.expected_category,
        output=result,
        duration=duration,
        _span_tree=SpanTreeRecordingError(
            "Spans not captured during manual evaluation run"
        ),
        attributes={},
        metrics={},
    )

    # Run each evaluator
    accuracy_eval = ClassificationAccuracyEval()
    efficiency_eval = EfficiencyEval()
    grounding_eval = GroundingEval()
    calibration_eval = CalibrationEval()
    overall_eval = OverallQualityEval()

    accuracy_result = accuracy_eval.evaluate(ctx)
    efficiency_result = efficiency_eval.evaluate(ctx)
    grounding_result = grounding_eval.evaluate(ctx)
    calibration_result = calibration_eval.evaluate(ctx)
    overall_result = overall_eval.evaluate(ctx)

    scores: dict[str, float] = {
        "accuracy": float(accuracy_result.value),
        "efficiency": float(efficiency_result.value),
        "grounding": float(grounding_result.value),
        "calibration": float(calibration_result.value),
    }

    # Extract overall composite scores
    if isinstance(overall_result, dict):
        for key, reason_obj in overall_result.items():
            scores[f"overall_{key}"] = float(reason_obj.value)

    return result, scores, duration


# =============================================================================
# Report Formatting
# =============================================================================


def print_case_result(
    case: EvalCase,
    result: ClassificationResult,
    scores: dict[str, float],
    duration: float,
) -> None:
    """Print a formatted result for a single evaluation case."""
    correct = result.category == case.expected_category
    status = "PASS" if correct else ("PARTIAL" if scores["accuracy"] == 0.5 else "FAIL")

    print(f"  [{status}] {case.name} ({case.difficulty})")
    print(
        f"    Expected: {case.expected_category.value:20s} | Got: {result.category.value}"
    )
    print(
        f"    Confidence: {result.confidence:.0%} | Questions: {result.questions_asked}"
    )
    print(
        f"    Scores: accuracy={scores['accuracy']:.2f}  "
        f"efficiency={scores['efficiency']:.2f}  "
        f"grounding={scores['grounding']:.2f}  "
        f"calibration={scores['calibration']:.2f}"
    )
    if "overall_overall" in scores:
        print(f"    Overall quality: {scores['overall_overall']:.3f}")
    print(f"    Duration: {duration:.1f}s")
    print()


def print_aggregate_report(
    all_scores: list[dict[str, float]],
    total_duration: float,
    cases: list[EvalCase],
) -> None:
    """Print aggregate metrics across all cases."""
    if not all_scores:
        print("  No results to aggregate.")
        return

    # Compute averages per metric
    metric_names = sorted(all_scores[0].keys())
    averages: dict[str, float] = {}
    for metric in metric_names:
        values = [s[metric] for s in all_scores if metric in s]
        averages[metric] = sum(values) / len(values) if values else 0.0

    # Count pass/partial/fail
    exact_correct = sum(1 for s in all_scores if s["accuracy"] == 1.0)
    partial_correct = sum(1 for s in all_scores if s["accuracy"] == 0.5)
    wrong = sum(1 for s in all_scores if s["accuracy"] == 0.0)
    total = len(all_scores)

    # Per-difficulty breakdown
    difficulty_groups: dict[str, list[dict[str, float]]] = {}
    for case, scores in zip(cases, all_scores):
        difficulty_groups.setdefault(case.difficulty, []).append(scores)

    print("=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    print()
    print(f"  Total cases:  {total}")
    print(f"  Exact match:  {exact_correct}/{total} ({exact_correct / total:.0%})")
    print(f"  Partial:      {partial_correct}/{total}")
    print(f"  Wrong:        {wrong}/{total}")
    print(f"  Total time:   {total_duration:.1f}s")
    print()

    print("  Average Scores:")
    print(f"    accuracy:    {averages.get('accuracy', 0):.3f}")
    print(f"    efficiency:  {averages.get('efficiency', 0):.3f}")
    print(f"    grounding:   {averages.get('grounding', 0):.3f}")
    print(f"    calibration: {averages.get('calibration', 0):.3f}")
    if "overall_overall" in averages:
        print(f"    overall:     {averages['overall_overall']:.3f}")
    print()

    print("  By Difficulty:")
    for difficulty in ["easy", "medium", "hard", "edge", "adversarial"]:
        group = difficulty_groups.get(difficulty, [])
        if not group:
            continue
        acc_avg = sum(s["accuracy"] for s in group) / len(group)
        eff_avg = sum(s["efficiency"] for s in group) / len(group)
        print(
            f"    {difficulty:12s}: "
            f"{len(group)} cases, "
            f"accuracy={acc_avg:.2f}, "
            f"efficiency={eff_avg:.2f}"
        )

    print()


# =============================================================================
# Main Runner
# =============================================================================


async def run_evaluation(
    dataset_path: Path,
    case_names: list[str] | None = None,
) -> None:
    """Run the full evaluation pipeline."""
    # Load cases
    all_cases = load_eval_cases(dataset_path)
    cases = filter_cases(all_cases, case_names)

    if not cases:
        print("No cases to evaluate.")
        return

    print("=" * 70)
    print("CAPSTONE EVALUATION: Private Securities Classification")
    print("=" * 70)
    print(f"  Dataset: {dataset_path}")
    print(f"  Cases:   {len(cases)} / {len(all_cases)}")
    print()

    # Set up shared dependencies
    deps = AnalystContext.create(analyst_name="Evaluator")

    all_results: list[
        tuple[EvalCase, ClassificationResult, dict[str, float], float]
    ] = []
    total_start = time.perf_counter()

    for i, case in enumerate(cases, 1):
        print(f"--- Case {i}/{len(cases)}: {case.name} ---")
        try:
            result, scores, duration = await evaluate_single_case(case, deps)
            print_case_result(case, result, scores, duration)
            all_results.append((case, result, scores, duration))
        except Exception as exc:
            print(f"  [ERROR] {case.name}: {type(exc).__name__}: {exc}")
            print()

    total_duration = time.perf_counter() - total_start

    # Aggregate report
    all_scores = [scores for _, _, scores, _ in all_results]
    evaluated_cases = [case for case, _, _, _ in all_results]
    print_aggregate_report(all_scores, total_duration, evaluated_cases)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate the private securities classification pipeline.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parent / "datasets" / "cases_v1.yaml",
        help="Path to the evaluation dataset YAML file.",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=None,
        help="Names of specific cases to run (default: all).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_evaluation(dataset_path=args.dataset, case_names=args.cases))


if __name__ == "__main__":
    main()
