"""
Module 09: Evals Fundamentals with pydantic-evals
===================================================

"Start with errors you DISCOVERED, not errors you IMAGINED."
    -- Hamel Husain

This module teaches pydantic-evals from the ground up. Evals are
the most important skill in applied AI engineering, yet they are
fundamentally different from traditional software testing.

Key distinction:
  - TESTS assert correctness on deterministic code. 100% pass or fail.
  - EVALS measure quality distributions on stochastic systems.
    A 90% pass rate might be acceptable. A 70% score on reasoning
    quality might be excellent for a hard task.

In Module 06, you discovered that the router agent sometimes misroutes
convertible instruments. Those DISCOVERED errors became your first
informal eval cases. Now we formalize them with pydantic-evals.

Sections:
  1. What Evals Are (Not Tests)
  2. Case and Dataset
  3. Built-in Evaluators
  4. Custom Evaluators
  5. Running Evaluations and Report Analysis

Exercise: Build a proper eval dataset with 10 cases for a securities
classification agent. Write a custom RoutingAccuracy evaluator. Run
and analyze the report.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
    EqualsExpected,
    IsInstance,
    # LLMJudge is covered in Module 10; imported here for reference
    LLMJudge,  # noqa: F401
)

from shared.models import SecurityCategory


# =============================================================================
# Section 1: What Evals Are (Not Tests)
# =============================================================================
# In traditional software:
#
#   def test_add():
#       assert add(2, 3) == 5  # deterministic, binary pass/fail
#
# With LLM-powered agents:
#
#   The same input can produce different outputs each run.
#   "Correct" is not always binary -- classification might be
#   partially right (convertible note vs. debt).
#   Quality exists on a spectrum: reasoning might be excellent,
#   mediocre, or terrible.
#
# Evals capture this reality:
#   - Run N cases through the agent
#   - Score each output on multiple dimensions
#   - Aggregate into a quality distribution
#   - Track trends over time (did the prompt change help?)
#
# A 90% accuracy on "easy" cases and 60% on "hard" cases
# is a perfectly valid eval result. The question is:
# is that good enough for production?


# =============================================================================
# Section 2: Case and Dataset
# =============================================================================
# A Case is a single input/expected-output pair with optional metadata.
# A Dataset is a collection of Cases plus evaluators that run on all of them.
#
# The type parameters are: Case[InputsT, OutputT, MetadataT]
#
# For our securities classification:
#   InputsT  = str           (the security description to classify)
#   OutputT  = str           (the category name returned by the agent)
#   MetadataT = dict         (difficulty level, notes, etc.)

# --- First, define the classification agent that we will evaluate ---

classification_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=SecurityCategory,
    system_prompt=(
        "You are a private securities classifier. Given a description of a "
        "private security, classify it into exactly one category. "
        "Choose from: equity, debt, convertible_note, safe, fund_interest, "
        "real_estate, revenue_share, other. "
        "Respond with ONLY the category value, nothing else."
    ),
)


# --- Build the eval dataset ---
# These cases come from DISCOVERED errors in Module 06's router,
# plus additional cases covering the full category space.
# Each case has a difficulty level in metadata.

securities_eval_dataset = Dataset(
    name="securities_classification_v1",
    cases=[
        # --- Easy: clear-cut securities ---
        Case(
            name="clear_debt_notes",
            inputs=(
                "Atlas Infrastructure Corp is offering $25M in 3-year senior "
                "secured notes bearing 8.5% annual interest, paid quarterly. "
                "Notes are secured by infrastructure assets."
            ),
            expected_output=SecurityCategory.DEBT,
            metadata={"difficulty": "easy", "source": "fake_data"},
        ),
        Case(
            name="clear_equity_preferred",
            inputs=(
                "Series B Preferred Stock offering. 1x non-participating "
                "liquidation preference. Anti-dilution protection. "
                "Pre-money valuation: $200M."
            ),
            expected_output=SecurityCategory.EQUITY,
            metadata={"difficulty": "easy", "source": "fake_data"},
        ),
        Case(
            name="clear_fund_interest",
            inputs=(
                "Meridian Growth Fund LP offers limited partnership interests "
                "in a diversified private equity fund targeting mid-market "
                "buyouts. Minimum investment of $250,000."
            ),
            expected_output=SecurityCategory.FUND_INTEREST,
            metadata={"difficulty": "easy", "source": "fake_data"},
        ),
        Case(
            name="clear_safe",
            inputs=(
                "NovaTech AI Inc is raising $5M via Simple Agreement for "
                "Future Equity (SAFE) instruments. 20% discount to next "
                "priced round, $20M valuation cap. Y Combinator standard "
                "SAFE terms."
            ),
            expected_output=SecurityCategory.SAFE,
            metadata={"difficulty": "easy", "source": "fake_data"},
        ),
        # --- Medium: requires some inference ---
        Case(
            name="real_estate_fund",
            inputs=(
                "Pacific Heights Residences Fund offers membership interests "
                "in a real estate investment vehicle targeting luxury "
                "multifamily properties in the Bay Area. Target IRR 15-18%. "
                "5-year hold period."
            ),
            expected_output=SecurityCategory.REAL_ESTATE,
            metadata={"difficulty": "medium", "source": "fake_data"},
        ),
        Case(
            name="revenue_share_agreement",
            inputs=(
                "Participate in Riverview's growth. Investors receive a share "
                "of monthly recurring revenue until 2x their investment is "
                "returned, then 0.5% of revenue in perpetuity. Not equity, "
                "not debt."
            ),
            expected_output=SecurityCategory.REVENUE_SHARE,
            metadata={"difficulty": "medium", "source": "fake_data"},
        ),
        Case(
            name="community_bonds",
            inputs=(
                "Community solar bonds funding installation of solar panels. "
                "4.5% annual coupon. 10-year maturity. Issued by an energy "
                "cooperative under Reg A+."
            ),
            expected_output=SecurityCategory.DEBT,
            metadata={"difficulty": "medium", "source": "fake_data"},
        ),
        # --- Hard: genuinely ambiguous (discovered errors from Module 06) ---
        Case(
            name="convertible_note_ambiguous",
            inputs=(
                "Convertible promissory note. 6% annual interest. "
                "Auto-converts at qualified financing of $5M+. "
                "25% discount or $15M valuation cap, whichever is more "
                "favorable to the holder."
            ),
            expected_output=SecurityCategory.CONVERTIBLE_NOTE,
            metadata={
                "difficulty": "hard",
                "source": "discovered_error_module06",
                "note": "Router often misroutes this to debt or equity",
            },
        ),
        Case(
            name="hybrid_instrument",
            inputs=(
                "Hybrid instrument paying 4% coupon with mandatory conversion "
                "to common equity at maturity. Functions as debt during term, "
                "becomes equity at maturity. 5-year duration."
            ),
            expected_output=SecurityCategory.CONVERTIBLE_NOTE,
            metadata={
                "difficulty": "hard",
                "source": "discovered_error_module06",
                "note": "Could be debt or convertible_note; has both features",
            },
        ),
        Case(
            name="token_offering_exotic",
            inputs=(
                "Token-based investment instrument. Tokens represent a claim "
                "on future protocol revenues. Not a security per issuer's "
                "legal opinion, but structured with investment contract "
                "characteristics."
            ),
            expected_output=SecurityCategory.OTHER,
            metadata={
                "difficulty": "hard",
                "source": "edge_case",
                "note": "Regulatory ambiguity; best classified as other",
            },
        ),
    ],
)


# =============================================================================
# Section 3: Built-in Evaluators
# =============================================================================
# pydantic-evals ships with several evaluators out of the box:
#
# - EqualsExpected: checks if output == expected_output (assertion: bool)
# - Equals(value): checks if output == a specific value
# - Contains(value): checks if output contains a value
# - IsInstance(type_name): checks if output is an instance of a type
# - MaxDuration(seconds): checks if execution was fast enough
# - LLMJudge(rubric): uses an LLM to judge output quality
# - HasMatchingSpan(query): checks OpenTelemetry spans
#
# Evaluators return different types:
#   bool   -> becomes an "assertion" (pass/fail in the report)
#   float  -> becomes a "score" (aggregated as averages)
#   str    -> becomes a "label" (shown as categories)
#   dict   -> multiple named results from one evaluator
#
# Let's add a few built-in evaluators to our dataset:

# EqualsExpected: the most basic check -- did the agent get the right answer?
securities_eval_dataset.add_evaluator(EqualsExpected())

# IsInstance: verify the output is the right type (sanity check)
securities_eval_dataset.add_evaluator(IsInstance(type_name="SecurityCategory"))

# LLMJudge example (commented out to avoid extra API calls during tutorial):
# This would use an LLM to judge whether the classification makes sense
# given the input description. Useful for cases where exact match is too strict.
#
# securities_eval_dataset.add_evaluator(
#     LLMJudge(
#         rubric=(
#             "The classification is reasonable for the described security. "
#             "Even if not an exact match, the category should be defensible."
#         ),
#         include_input=True,
#         include_expected_output=True,
#     )
# )


# =============================================================================
# Section 4: Custom Evaluators
# =============================================================================
# Custom evaluators subclass Evaluator and implement evaluate().
# They MUST be decorated with @dataclass.
#
# The evaluate method receives an EvaluatorContext with:
#   ctx.inputs          - the case inputs
#   ctx.output          - what the task actually returned
#   ctx.expected_output - what we expected (may be None)
#   ctx.metadata        - case metadata (difficulty, source, etc.)
#   ctx.duration        - how long the task took
#   ctx.metrics         - any recorded metrics
#   ctx.attributes      - any recorded attributes
#
# Return types determine how results appear in the report:
#   bool   -> assertion (pass/fail)
#   float  -> score (averaged)
#   str    -> label (categorized)
#   dict   -> multiple named results
#   EvaluationReason(value, reason) -> any of the above with an explanation


@dataclass
class RoutingAccuracy(Evaluator[str, SecurityCategory]):
    """Check if the classification matches expected, with partial credit for related categories.

    This evaluator was born from a DISCOVERED error: the Module 06 router
    sometimes classifies convertible notes as plain debt. That is "close"
    but not exact. Rather than binary pass/fail, we give partial credit
    for related categories.

    Returns a float score: 1.0 (exact), 0.5 (related), 0.0 (wrong).
    """

    # Related categories that earn partial credit
    RELATED: dict[SecurityCategory, set[SecurityCategory]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.RELATED is None:
            self.RELATED = {
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
                SecurityCategory.DEBT: {
                    SecurityCategory.CONVERTIBLE_NOTE,
                },
            }

    def evaluate(self, ctx: EvaluatorContext[str, SecurityCategory]) -> EvaluatorOutput:
        if ctx.expected_output is None:
            return {}

        actual = ctx.output
        expected = ctx.expected_output

        if actual == expected:
            return {"accuracy": 1.0, "accuracy_label": "exact"}

        related = self.RELATED.get(expected, set())
        if actual in related:
            return {"accuracy": 0.5, "accuracy_label": "related"}

        return {"accuracy": 0.0, "accuracy_label": "wrong"}


@dataclass
class DifficultyAwareAccuracy(Evaluator[str, SecurityCategory]):
    """Score accuracy weighted by difficulty level from metadata.

    Easy cases should always be correct (harsh scoring).
    Hard cases get more lenient scoring (partial credit).

    This evaluator demonstrates using metadata in evaluation.
    """

    def evaluate(self, ctx: EvaluatorContext[str, SecurityCategory]) -> EvaluatorOutput:
        if ctx.expected_output is None or ctx.metadata is None:
            return {}

        is_correct = ctx.output == ctx.expected_output
        difficulty = ctx.metadata.get("difficulty", "medium")

        if difficulty == "easy":
            # Easy cases: strict scoring. Wrong answer on easy = 0.0.
            return 1.0 if is_correct else 0.0
        elif difficulty == "hard":
            # Hard cases: partial credit for getting close.
            # Even getting it wrong is less penalized.
            return 1.0 if is_correct else 0.3
        else:
            # Medium: standard scoring
            return 1.0 if is_correct else 0.1


# Add our custom evaluators to the dataset
securities_eval_dataset.add_evaluator(RoutingAccuracy())
securities_eval_dataset.add_evaluator(DifficultyAwareAccuracy())


# =============================================================================
# Section 5: Running Evaluations and Report Analysis
# =============================================================================
# To run evals, you need a "task function" that takes the case inputs
# and returns the output. This is the function being evaluated.
#
# dataset.evaluate_sync(task_function) runs all cases and returns a report.
# The report has:
#   - Per-case results (assertions, scores, labels, metrics)
#   - Aggregate averages across all cases
#   - Duration information
#   - A .print() method for rich terminal output


async def classify_security(description: str) -> SecurityCategory:
    """The task function: classify a security description into a category.

    This is the function we are evaluating. It calls the pydantic-ai agent
    and returns the classification result.
    """
    result = await classification_agent.run(description)
    return result.output


async def main() -> None:
    print("=" * 70)
    print("MODULE 09: EVALS FUNDAMENTALS")
    print("Measure quality distributions, not binary pass/fail")
    print("=" * 70)
    print()

    # --- Demo 1: Inspect the dataset ---
    print("--- Dataset Overview ---")
    print(f"Dataset name: {securities_eval_dataset.name}")
    print(f"Number of cases: {len(securities_eval_dataset.cases)}")
    print(f"Number of evaluators: {len(securities_eval_dataset.evaluators)}")
    print()

    for case in securities_eval_dataset.cases:
        difficulty = case.metadata.get("difficulty", "?") if case.metadata else "?"
        print(f"  [{difficulty:6s}] {case.name}")
        print(f"           Expected: {case.expected_output}")
    print()

    # --- Demo 2: Run the evaluation ---
    print("--- Running Evaluation ---")
    print("Calling classification agent on all 10 cases...")
    print("(This makes real API calls)")
    print()

    report = securities_eval_dataset.evaluate_sync(
        classify_security,
        name="securities_classification_eval",
        max_concurrency=3,  # Limit concurrent API calls
    )

    # --- Demo 3: Print the report ---
    print("--- Evaluation Report ---")
    print()
    report.print(
        include_input=False,  # Inputs are long; skip for readability
        include_output=True,  # Show what the agent actually returned
        include_expected_output=True,  # Show what we expected
        include_reasons=True,  # Show evaluator reasoning
    )
    print()

    # --- Demo 4: Analyze the report programmatically ---
    print("--- Programmatic Report Analysis ---")
    print()

    averages = report.averages()
    if averages:
        print(f"  Overall assertions pass rate: {averages.assertions}")
        print(f"  Average scores: {averages.scores}")
        print(f"  Label distribution: {averages.labels}")
        print(f"  Average task duration: {averages.task_duration:.2f}s")
    print()

    # Per-case analysis
    easy_correct = 0
    easy_total = 0
    hard_correct = 0
    hard_total = 0

    for case in report.cases:
        # Access the original metadata through the case inputs
        # The report case has the metadata from the original Case
        metadata = case.metadata or {}
        difficulty = metadata.get("difficulty", "medium")
        is_correct = case.output == case.expected_output

        if difficulty == "easy":
            easy_total += 1
            easy_correct += int(is_correct)
        elif difficulty == "hard":
            hard_total += 1
            hard_correct += int(is_correct)

    if easy_total > 0:
        print(
            f"  Easy cases:  {easy_correct}/{easy_total} = {easy_correct / easy_total:.0%}"
        )
    if hard_total > 0:
        print(
            f"  Hard cases:  {hard_correct}/{hard_total} = {hard_correct / hard_total:.0%}"
        )
    print()

    # Check for failures (cases where the task function raised an exception)
    if report.failures:
        print(f"  WARNING: {len(report.failures)} case(s) failed with exceptions:")
        for failure in report.failures:
            print(f"    {failure.name}: {failure.error_message}")
    else:
        print("  No task execution failures.")
    print()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. Evals measure quality distributions, not binary correctness")
    print("  2. Case = inputs + expected_output + metadata")
    print("  3. Dataset = cases + evaluators, evaluated against a task function")
    print("  4. Built-in evaluators: EqualsExpected, IsInstance, LLMJudge, etc.")
    print("  5. Custom evaluators: @dataclass class + evaluate() method")
    print("  6. report.print() for rich output; report.averages() for analysis")
    print()
    print("EVAL PHILOSOPHY (Hamel Husain):")
    print("  The convertible_note and hybrid_instrument cases came from")
    print("  DISCOVERED errors in Module 06. We did not imagine them --")
    print("  we ran the agent, saw it fail, and codified those failures")
    print("  into eval cases. That is the right workflow.")
    print()
    print("Next: Module 10 -- LLMJudge, model comparison, YAML serialization")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
