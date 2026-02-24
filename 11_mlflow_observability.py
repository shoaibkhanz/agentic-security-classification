"""
Module 11: MLflow Observability
================================

MLflow provides full observability for your agent pipeline:
  - Automatic tracing of every LLM call, tool invocation, and agent decision
  - Experiment tracking for comparing models and configurations
  - Metrics logging for eval results
  - Visual UI for exploring traces

One line of code — `mlflow.pydantic_ai.autolog()` — captures everything.

Sections:
  1. Setup and Autolog
  2. Tracing Agent Runs
  3. Experiment Tracking
  4. Logging Eval Metrics
  5. Viewing Results in MLflow UI
"""

from __future__ import annotations

import asyncio

import mlflow
import mlflow.pydantic_ai
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from shared.deps import SecuritiesDB
from shared.models import SecurityCategory


# =============================================================================
# Section 1: Setup and Autolog
# =============================================================================
# mlflow.pydantic_ai.autolog() is all you need.
# It automatically instruments:
#   - Agent.run() and Agent.run_sync() calls
#   - Every LLM request (model, prompt, parameters, response)
#   - Every tool invocation (name, args, result)
#   - Token usage per call
#   - Nested traces for multi-agent pipelines
#
# No code changes to your agents. Just add this line.

# Set up MLflow to use a local directory for tracking
# In production, you'd point to a tracking server
mlflow.set_tracking_uri("mlruns")
mlflow.set_experiment("securities-classification-tutorial")

# Enable automatic tracing for pydantic-ai
mlflow.pydantic_ai.autolog()


# =============================================================================
# Section 2: Tracing Agent Runs
# =============================================================================
# With autolog enabled, every agent.run() is automatically traced.
# The trace captures the full execution tree:
#   Agent Run
#   ├── LLM Request (prompt, model, params)
#   │   └── LLM Response (content, tokens)
#   ├── Tool Call: search_securities
#   │   └── Tool Result
#   └── LLM Request (with tool results)
#       └── LLM Response (final answer)


class QuickClassification(BaseModel):
    """Simple classification for tracing demo."""

    category: SecurityCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


classification_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    deps_type=SecuritiesDB,
    output_type=QuickClassification,
    system_prompt=(
        "You classify private securities. Use the search tool to find "
        "information, then classify with confidence and reasoning."
    ),
)


@classification_agent.tool
async def search_db(ctx: RunContext[SecuritiesDB], query: str) -> str:
    """Search the securities database."""
    results = await ctx.deps.search(query)
    if not results:
        return f"No results for '{query}'"
    sec = results[0]
    return (
        f"Found: {sec.name} | Issuer: {sec.issuer} | "
        f"Type: {sec.type_hint or 'unknown'} | "
        f"Description: {sec.raw_description[:200]}"
    )


async def demo_tracing() -> None:
    """Run an agent with automatic tracing."""
    print("--- Tracing Agent Runs ---")
    print("(Every call is automatically captured by MLflow)\n")

    db = SecuritiesDB()

    # This run is automatically traced by mlflow.pydantic_ai.autolog()
    result = await classification_agent.run(
        "Classify the NovaTech SAFE Round",
        deps=db,
    )

    print(f"  Category: {result.output.category.value}")
    print(f"  Confidence: {result.output.confidence:.0%}")
    print(f"  Reasoning: {result.output.reasoning[:150]}...")
    print(f"  Usage: {result.usage()}")
    print()
    print("  Trace captured automatically! View in MLflow UI.")
    print()


# =============================================================================
# Section 3: Experiment Tracking
# =============================================================================
# Use MLflow runs to organize experiments.
# Each run captures: parameters, metrics, traces, and artifacts.


async def demo_experiment_tracking() -> None:
    """Track multiple classifications as an experiment."""
    print("--- Experiment Tracking ---\n")

    db = SecuritiesDB()

    test_queries = [
        "Classify Atlas Senior Secured Notes 2024",
        "Classify Meridian Growth Fund LP",
        "Classify Cascade SAFE+Note",
    ]

    for query in test_queries:
        # Each classification gets its own MLflow run
        with mlflow.start_run(run_name=query[:40]):
            # Log parameters
            mlflow.log_param("query", query)
            mlflow.log_param("model", "sonnet-4-5")

            # Run the agent (traced automatically)
            result = await classification_agent.run(query, deps=db)

            # Log metrics
            mlflow.log_metric("confidence", result.output.confidence)
            mlflow.log_metric("total_tokens", result.usage().total_tokens or 0)

            # Log classification as a tag
            mlflow.set_tag("category", result.output.category.value)

            print(f"  {query}")
            print(
                f"    → {result.output.category.value} ({result.output.confidence:.0%})"
            )

    print()
    print(
        "  All runs tracked in MLflow experiment: 'securities-classification-tutorial'"
    )
    print()


# =============================================================================
# Section 4: Logging Eval Metrics
# =============================================================================
# Combine MLflow with pydantic-evals: run evaluations and log
# the results as MLflow metrics for comparison across experiments.


async def demo_eval_logging() -> None:
    """Log evaluation metrics to MLflow."""
    print("--- Logging Eval Metrics ---\n")

    # Simulate eval results (in practice, use pydantic-evals dataset.evaluate_sync)
    eval_results = {
        "classification_accuracy": 0.85,
        "avg_confidence": 0.78,
        "routing_accuracy": 0.90,
        "avg_questions_asked": 3.2,
        "evidence_grounding": 0.92,
    }

    with mlflow.start_run(run_name="eval-sonnet"):
        mlflow.log_param("model", "sonnet-4-5")
        mlflow.log_param("eval_cases", 10)
        mlflow.log_param("eval_type", "classification")

        for metric_name, value in eval_results.items():
            mlflow.log_metric(metric_name, value)
            print(f"  Logged: {metric_name} = {value}")

    print()
    print("  Metrics logged to MLflow. Compare across model versions in UI.")
    print()


# =============================================================================
# Section 5: Viewing Results in MLflow UI
# =============================================================================
# To view traces and experiments:
#
#   uv run mlflow server --port 5000
#
# Then open http://localhost:5000 in your browser.
#
# What you'll see:
#   - Experiments list with all your runs
#   - Each run shows: parameters, metrics, traces
#   - Traces show the full execution tree:
#     - Agent run → LLM requests → tool calls → responses
#   - Compare metrics across runs (e.g., different models)
#   - Token usage and latency per trace


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 11: MLFLOW OBSERVABILITY")
    print("One line of code for full agent visibility")
    print("=" * 70)
    print()

    # Demo 1: Automatic tracing
    await demo_tracing()

    # Demo 2: Experiment tracking
    await demo_experiment_tracking()

    # Demo 3: Eval metrics logging
    await demo_eval_logging()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. mlflow.pydantic_ai.autolog() — one line, full tracing")
    print("  2. Every LLM call, tool invocation, and result is captured")
    print("  3. mlflow.start_run() organizes experiments")
    print("  4. Log eval metrics for cross-model comparison")
    print("  5. MLflow UI: `uv run mlflow server --port 5000`")
    print()
    print("PRODUCTION PATTERNS:")
    print("  - autolog() in your app startup (zero code changes)")
    print("  - Log eval metrics per model version")
    print("  - Compare traces to debug routing/reasoning issues")
    print("  - Track token costs per experiment")
    print()
    print("VIEW YOUR TRACES:")
    print("  Run: uv run mlflow server --port 5000")
    print("  Open: http://localhost:5000")
    print()
    print("Next: Capstone — Private Securities Classification Agent")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
