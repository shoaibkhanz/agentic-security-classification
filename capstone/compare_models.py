"""
Model comparison script for the classification pipeline.

Run with:
    uv run python -m capstone.compare_models
    uv run python -m capstone.compare_models --models anthropic:sonnet-4-5-20250929 openai:gpt-4o
    uv run python -m capstone.compare_models --cases atlas_senior_notes novatech_safe

Compares classification quality across different LLM backends by:
  1. Running the pipeline with each model (overriding all agents)
  2. Scoring with the capstone evaluators
  3. Logging metrics to MLflow for tracking
  4. Printing a comparison table

Production note: To use OpenAI models, set OPENAI_API_KEY in your
environment. To use Anthropic models, set ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import mlflow
import mlflow.pydantic_ai

from capstone.agents import (
    classifier,
    confidence_assessor,
    initial_assessor,
    question_planner,
    researcher,
    verifier,
)
from capstone.evaluate import load_eval_cases, filter_cases
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
from shared.models import ClassificationResult


# =============================================================================
# All agents in the pipeline (for model override)
# =============================================================================

ALL_AGENTS = [
    question_planner,
    initial_assessor,
    researcher,
    confidence_assessor,
    classifier,
    verifier,
]


# =============================================================================
# Evaluate a single case with a specific model
# =============================================================================


async def evaluate_case_with_model(
    case: EvalCase,
    deps: AnalystContext,
) -> tuple[ClassificationResult, dict[str, float], float]:
    """
    Run the classification pipeline on a case (agents already overridden)
    and return (result, scores, duration).
    """
    from pydantic_evals.evaluators.context import EvaluatorContext
    from pydantic_evals.otel._errors import SpanTreeRecordingError

    start = time.perf_counter()

    result, state = await classify_security(
        description=case.security_description,
        deps=deps,
        confidence_threshold=0.82,
        max_actions=case.expected_max_questions + 3,
    )

    duration = time.perf_counter() - start

    ctx = EvaluatorContext(
        name=case.name,
        inputs=case.security_description,
        metadata=case,
        expected_output=case.expected_category,
        output=result,
        duration=duration,
        _span_tree=SpanTreeRecordingError("Spans not captured during model comparison"),
        attributes={},
        metrics={},
    )

    accuracy_result = ClassificationAccuracyEval().evaluate(ctx)
    efficiency_result = EfficiencyEval().evaluate(ctx)
    grounding_result = GroundingEval().evaluate(ctx)
    calibration_result = CalibrationEval().evaluate(ctx)
    overall_result = OverallQualityEval().evaluate(ctx)

    scores: dict[str, float] = {
        "accuracy": float(accuracy_result.value),
        "efficiency": float(efficiency_result.value),
        "grounding": float(grounding_result.value),
        "calibration": float(calibration_result.value),
    }

    if isinstance(overall_result, dict):
        for key, reason_obj in overall_result.items():
            scores[f"overall_{key}"] = float(reason_obj.value)

    return result, scores, duration


# =============================================================================
# Run all cases for one model
# =============================================================================


async def run_model_evaluation(
    model_name: str,
    cases: list[EvalCase],
    deps: AnalystContext,
) -> list[tuple[EvalCase, ClassificationResult, dict[str, float], float]]:
    """
    Run the full evaluation suite for a single model.

    Overrides all agents to use the specified model, then runs each case.
    """
    # Create override contexts for all agents
    overrides = [agent.override(model=model_name) for agent in ALL_AGENTS]

    results: list[tuple[EvalCase, ClassificationResult, dict[str, float], float]] = []

    # Enter all override contexts
    # Using nested context managers via a manual stack
    import contextlib

    async with contextlib.AsyncExitStack() as stack:
        for override in overrides:
            stack.enter_context(override)

        for i, case in enumerate(cases, 1):
            print(
                f"    [{model_name}] Case {i}/{len(cases)}: {case.name} ... ",
                end="",
                flush=True,
            )
            try:
                result, scores, duration = await evaluate_case_with_model(case, deps)
                status = (
                    "PASS"
                    if scores["accuracy"] == 1.0
                    else ("PARTIAL" if scores["accuracy"] == 0.5 else "FAIL")
                )
                print(f"{status} ({duration:.1f}s)")
                results.append((case, result, scores, duration))
            except Exception as exc:
                print(f"ERROR: {type(exc).__name__}: {exc}")

    return results


# =============================================================================
# MLflow Logging
# =============================================================================


def log_model_results_to_mlflow(
    model_name: str,
    results: list[tuple[EvalCase, ClassificationResult, dict[str, float], float]],
) -> None:
    """Log evaluation results for a model to MLflow."""
    if not results:
        return

    all_scores = [scores for _, _, scores, _ in results]
    total_duration = sum(d for _, _, _, d in results)

    # Compute aggregates
    metric_names = ["accuracy", "efficiency", "grounding", "calibration"]
    aggregates: dict[str, float] = {}
    for metric in metric_names:
        values = [s[metric] for s in all_scores if metric in s]
        aggregates[metric] = sum(values) / len(values) if values else 0.0

    if "overall_overall" in all_scores[0]:
        overall_values = [s["overall_overall"] for s in all_scores]
        aggregates["overall"] = sum(overall_values) / len(overall_values)

    # Exact match rate
    exact_correct = sum(1 for s in all_scores if s["accuracy"] == 1.0)
    aggregates["exact_match_rate"] = exact_correct / len(all_scores)
    aggregates["total_duration_seconds"] = total_duration
    aggregates["cases_evaluated"] = float(len(results))

    with mlflow.start_run(run_name=model_name):
        mlflow.log_param("model", model_name)
        mlflow.log_param("num_cases", len(results))

        for metric_name, metric_value in aggregates.items():
            mlflow.log_metric(metric_name, metric_value)

        # Log per-case accuracy as a table artifact
        for case, result, scores, duration in results:
            case_metrics = {
                f"{case.name}_accuracy": scores["accuracy"],
                f"{case.name}_confidence": result.confidence,
                f"{case.name}_questions": float(result.questions_asked),
                f"{case.name}_duration": duration,
            }
            mlflow.log_metrics(case_metrics)


# =============================================================================
# Comparison Table
# =============================================================================


def print_comparison_table(
    model_results: dict[
        str, list[tuple[EvalCase, ClassificationResult, dict[str, float], float]]
    ],
) -> None:
    """Print a formatted comparison table across models."""
    models = list(model_results.keys())
    if not models:
        return

    print()
    print("=" * 80)
    print("MODEL COMPARISON")
    print("=" * 80)
    print()

    # Header
    header = f"  {'Metric':<25}"
    for model in models:
        # Truncate long model names for display
        display_name = model.split(":")[-1][:20] if ":" in model else model[:20]
        header += f" {display_name:>15}"
    print(header)
    print("  " + "-" * (25 + 16 * len(models)))

    # Aggregate metrics per model
    model_aggregates: dict[str, dict[str, float]] = {}
    for model_name, results in model_results.items():
        all_scores = [scores for _, _, scores, _ in results]
        if not all_scores:
            model_aggregates[model_name] = {}
            continue

        agg: dict[str, float] = {}
        for metric in ["accuracy", "efficiency", "grounding", "calibration"]:
            values = [s[metric] for s in all_scores if metric in s]
            agg[metric] = sum(values) / len(values) if values else 0.0

        if "overall_overall" in all_scores[0]:
            values = [s["overall_overall"] for s in all_scores]
            agg["overall_quality"] = sum(values) / len(values)

        exact = sum(1 for s in all_scores if s["accuracy"] == 1.0)
        agg["exact_match_rate"] = exact / len(all_scores)
        agg["avg_duration_sec"] = sum(d for _, _, _, d in results) / len(results)
        agg["total_cases"] = float(len(results))

        model_aggregates[model_name] = agg

    # Rows
    display_metrics = [
        "total_cases",
        "exact_match_rate",
        "accuracy",
        "efficiency",
        "grounding",
        "calibration",
        "overall_quality",
        "avg_duration_sec",
    ]

    for metric in display_metrics:
        row = f"  {metric:<25}"
        for model in models:
            value = model_aggregates.get(model, {}).get(metric)
            if value is None:
                row += f" {'N/A':>15}"
            elif metric == "total_cases":
                row += f" {int(value):>15}"
            elif metric == "avg_duration_sec":
                row += f" {value:>14.1f}s"
            else:
                row += f" {value:>15.3f}"
        print(row)

    print()

    # Per-case comparison
    print("  Per-Case Accuracy:")
    # Get case names from first model's results
    first_results = model_results[models[0]]
    for case, _, _, _ in first_results:
        row = f"    {case.name:<23}"
        for model in models:
            model_result_list = model_results[model]
            case_scores = next(
                (s for c, _, s, _ in model_result_list if c.name == case.name),
                None,
            )
            if case_scores is None:
                row += f" {'N/A':>15}"
            else:
                acc = case_scores["accuracy"]
                marker = "ok" if acc == 1.0 else ("~" if acc == 0.5 else "X")
                row += f" {acc:>12.1f} ({marker})"
        print(row)

    print()


# =============================================================================
# Main
# =============================================================================


async def run_comparison(
    models: list[str],
    dataset_path: Path,
    case_names: list[str] | None = None,
) -> None:
    """Run the full model comparison pipeline."""
    # Load cases
    all_cases = load_eval_cases(dataset_path)
    cases = filter_cases(all_cases, case_names)

    if not cases:
        print("No cases to evaluate.")
        return

    print("=" * 80)
    print("CAPSTONE MODEL COMPARISON")
    print("=" * 80)
    print(f"  Models:  {', '.join(models)}")
    print(f"  Cases:   {len(cases)}")
    print(f"  Dataset: {dataset_path}")
    print()

    # Enable MLflow pydantic-ai autologging for tracing
    mlflow.pydantic_ai.autolog()

    # Set up MLflow experiment
    experiment_name = "capstone-model-comparison"
    mlflow.set_experiment(experiment_name)
    print(f"  MLflow experiment: {experiment_name}")
    print("  View results: mlflow server --port 5000")
    print()

    deps = AnalystContext.create(analyst_name="Model Comparison")

    model_results: dict[
        str,
        list[tuple[EvalCase, ClassificationResult, dict[str, float], float]],
    ] = {}

    for model_name in models:
        print(f"--- Evaluating model: {model_name} ---")
        results = await run_model_evaluation(model_name, cases, deps)
        model_results[model_name] = results

        # Log to MLflow
        log_model_results_to_mlflow(model_name, results)

        print()

    # Print comparison
    print_comparison_table(model_results)

    print("  MLflow tracking:")
    print(f"    Experiment: {experiment_name}")
    print(f"    Runs logged: {len(models)}")
    print("    Start UI: uv run mlflow server --port 5000")
    print()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare LLM models on the securities classification pipeline.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "anthropic:sonnet-4-5-20250929",
            "openai:gpt-4o",
        ],
        help=(
            "Model identifiers to compare. "
            "Default: anthropic:sonnet-4-5-20250929 openai:gpt-4o. "
            "Note: Each model requires its API key in the environment "
            "(ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)."
        ),
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
    asyncio.run(
        run_comparison(
            models=args.models,
            dataset_path=args.dataset,
            case_names=args.cases,
        )
    )


if __name__ == "__main__":
    main()
