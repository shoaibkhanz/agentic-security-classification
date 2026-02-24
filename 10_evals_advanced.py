"""
Module 10: Advanced Evals -- LLMJudge, Model Comparison, Serialization
=======================================================================

This module builds on Module 09's foundations to cover the advanced
patterns that make evals a sustainable engineering practice:

1. LLMJudge -- when exact match is too strict and you need an LLM
   to assess quality against a rubric
2. Model comparison -- run the same dataset against different models
   to make informed model selection decisions
3. Dataset serialization -- save datasets to YAML for version control,
   collaboration, and CI/CD pipelines
4. Judge validation -- "Who validates the validators?" (Shreya Shankar)

The meta-lesson: evals are a living system. They evolve as your
understanding of failure modes deepens.

Sections:
  1. LLMJudge with Rubrics
  2. Model Comparison with agent.override()
  3. Dataset Serialization (YAML)
  4. Validating the Judge
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
    EqualsExpected,
    LLMJudge,
)

from shared.models import SecurityCategory


# =============================================================================
# Shared: Classification Agent (same as Module 09)
# =============================================================================

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


async def classify_security(description: str) -> SecurityCategory:
    """Task function: classify a security description into a category."""
    result = await classification_agent.run(description)
    return result.output


# =============================================================================
# Section 1: LLMJudge with Rubrics
# =============================================================================
# When exact match is too strict, LLMJudge uses an LLM to assess whether
# the output satisfies a rubric. This is essential for:
#
#   - Subjective quality (is the reasoning "good enough"?)
#   - Semantic equivalence (SAFE vs safe vs "Simple Agreement for Future Equity")
#   - Partial correctness (convertible_note is "close" to debt)
#
# LLMJudge configuration:
#   rubric:                 The criteria for the LLM to judge against
#   include_input:          Whether to show the input to the judge
#   include_expected_output: Whether to show expected output to the judge
#   model:                  Which model to use as judge (default: openai:gpt-4o)
#   score:                  OutputConfig or False. If not False, emit a score.
#   assertion:              OutputConfig or False. If not False, emit a pass/fail.
#
# By default, LLMJudge emits an assertion (pass/fail with reason).
# Set score=OutputConfig() to also get a numeric score (0.0 to 1.0).

# --- Build a dataset with LLMJudge evaluators ---

llm_judge_dataset = Dataset(
    name="securities_with_llm_judge",
    cases=[
        Case(
            name="clear_debt",
            inputs=(
                "Atlas Infrastructure Corp: $25M in 3-year senior secured "
                "notes at 8.5% annual interest, paid quarterly."
            ),
            expected_output=SecurityCategory.DEBT,
            metadata={"difficulty": "easy"},
        ),
        Case(
            name="clear_safe",
            inputs=(
                "NovaTech AI: $5M via SAFE instruments, 20% discount to "
                "next priced round, $20M valuation cap."
            ),
            expected_output=SecurityCategory.SAFE,
            metadata={"difficulty": "easy"},
        ),
        Case(
            name="convertible_note",
            inputs=(
                "Catalyst Biotech: Convertible promissory note, 6% interest, "
                "auto-converts at $5M+ financing, 25% discount or $15M cap."
            ),
            expected_output=SecurityCategory.CONVERTIBLE_NOTE,
            metadata={"difficulty": "hard"},
        ),
        Case(
            name="hybrid_mandatory_convert",
            inputs=(
                "Apex Financial: Hybrid instrument paying 4% coupon with "
                "mandatory conversion to common equity at maturity. "
                "Functions as debt during term, becomes equity at 5-year maturity."
            ),
            expected_output=SecurityCategory.CONVERTIBLE_NOTE,
            metadata={"difficulty": "hard"},
        ),
        Case(
            name="revenue_share",
            inputs=(
                "Riverview SaaS: Investors receive a share of monthly recurring "
                "revenue until 2x returned, then 0.5% in perpetuity. "
                "Explicitly not equity and not debt."
            ),
            expected_output=SecurityCategory.REVENUE_SHARE,
            metadata={"difficulty": "medium"},
        ),
        Case(
            name="real_estate_fund",
            inputs=(
                "Pacific Heights: Membership interests in a real estate "
                "vehicle targeting luxury multifamily Bay Area properties. "
                "Target IRR 15-18%, 5-year hold."
            ),
            expected_output=SecurityCategory.REAL_ESTATE,
            metadata={"difficulty": "medium"},
        ),
    ],
    evaluators=[
        # Exact match -- the baseline
        EqualsExpected(),
    ],
)

# Add LLMJudge: is the classification defensible?
# This catches cases where the exact category differs but the answer is reasonable.
# For example, classifying a mandatory-convert hybrid as "debt" is defensible
# even though we expected "convertible_note".
llm_judge_dataset.add_evaluator(
    LLMJudge(
        rubric=(
            "The classification is a reasonable and defensible categorization "
            "for the described security. If the expected output and actual "
            "output are related categories (e.g., convertible_note vs debt "
            "for something with both features), the classification should "
            "still pass. Only fail if the classification is clearly wrong "
            "(e.g., classifying clear debt as equity)."
        ),
        include_input=True,
        include_expected_output=True,
        model="anthropic:sonnet-4-5-20250929",
    )
)

# Add a second LLMJudge focused on a different rubric: reasoning quality.
# This one does NOT get the expected output -- it judges purely on whether
# the output "makes sense" given the input.
llm_judge_dataset.add_evaluator(
    LLMJudge(
        rubric=(
            "The classification makes sense given the security description. "
            "A knowledgeable securities analyst would agree this is at least "
            "a plausible category for the described instrument."
        ),
        include_input=True,
        include_expected_output=False,
        model="anthropic:sonnet-4-5-20250929",
    )
)


# =============================================================================
# Section 2: Model Comparison with agent.override()
# =============================================================================
# One of the most valuable uses of evals: comparing models.
#
# pydantic-ai's agent.override() context manager lets you swap the model
# at runtime without changing any code. Combined with pydantic-evals,
# you can run the exact same dataset against different models and compare.
#
# Pattern:
#   with agent.override(model='openai:gpt-4o'):
#       report_gpt = dataset.evaluate_sync(task, name='gpt-4o')
#
#   with agent.override(model='anthropic:sonnet-4-5-20250929'):
#       report = dataset.evaluate_sync(task, name='sonnet')
#
# Then compare report_gpt vs report side by side.

# A simpler dataset without LLMJudge for faster model comparison
comparison_dataset = Dataset(
    name="model_comparison_v1",
    cases=[
        Case(
            name="clear_debt",
            inputs="Senior secured notes, 8.5% annual interest, 3-year maturity, infrastructure collateral.",
            expected_output=SecurityCategory.DEBT,
            metadata={"difficulty": "easy"},
        ),
        Case(
            name="clear_equity",
            inputs="Series B Preferred Stock, 1x liquidation preference, anti-dilution, $200M pre-money.",
            expected_output=SecurityCategory.EQUITY,
            metadata={"difficulty": "easy"},
        ),
        Case(
            name="safe_instrument",
            inputs="SAFE with 20% discount and $20M cap, Y Combinator standard terms.",
            expected_output=SecurityCategory.SAFE,
            metadata={"difficulty": "easy"},
        ),
        Case(
            name="convertible_note",
            inputs="Convertible note, 6% interest, converts at Series A, 25% discount or $15M cap.",
            expected_output=SecurityCategory.CONVERTIBLE_NOTE,
            metadata={"difficulty": "hard"},
        ),
        Case(
            name="revenue_participation",
            inputs="Revenue share: 5% of monthly revenue until 2x returned, then 0.5% perpetually. Not equity, not debt.",
            expected_output=SecurityCategory.REVENUE_SHARE,
            metadata={"difficulty": "medium"},
        ),
    ],
    evaluators=[EqualsExpected()],
)


# =============================================================================
# Section 3: Dataset Serialization (YAML)
# =============================================================================
# Datasets can be saved to YAML (or JSON) and loaded back.
# This is critical for:
#
#   - Version control: track eval datasets in git
#   - Collaboration: share eval cases across the team
#   - CI/CD: run evals automatically on code changes
#   - Reproducibility: exact same cases, any time
#
# Methods:
#   dataset.to_file(Path("cases_v1.yaml"))
#   loaded = Dataset[str, SecurityCategory, dict].from_file(Path("cases_v1.yaml"))
#
# Custom evaluators need to be passed via custom_evaluator_types
# so the deserializer knows how to reconstruct them.

DATASETS_DIR = Path(__file__).parent / "datasets"


def demo_serialization() -> None:
    """Demonstrate saving and loading datasets as YAML."""
    print("--- Dataset Serialization ---")
    print()

    # Ensure the datasets directory exists
    DATASETS_DIR.mkdir(exist_ok=True)

    # Save to YAML (uses the simpler comparison dataset -- no custom evaluators)
    yaml_path = DATASETS_DIR / "securities_comparison_v1.yaml"
    comparison_dataset.to_file(yaml_path)
    print(f"  Saved dataset to: {yaml_path}")

    # Load it back
    loaded = Dataset[str, SecurityCategory, dict].from_file(yaml_path)
    print(f"  Loaded dataset: {loaded.name}")
    print(f"  Number of cases: {len(loaded.cases)}")
    print(f"  Number of evaluators: {len(loaded.evaluators)}")
    print()

    # Show the YAML contents
    yaml_content = yaml_path.read_text()
    print("  YAML contents (first 40 lines):")
    for i, line in enumerate(yaml_content.splitlines()[:40]):
        print(f"    {line}")
    print()

    # Verify round-trip integrity
    for original, loaded_case in zip(comparison_dataset.cases, loaded.cases):
        assert original.name == loaded_case.name, (
            f"Name mismatch: {original.name} != {loaded_case.name}"
        )
        assert original.inputs == loaded_case.inputs, (
            f"Input mismatch for {original.name}"
        )
    print("  Round-trip integrity verified: all cases match.")
    print()


# =============================================================================
# Section 4: Validating the Judge
# =============================================================================
# "Who Validates the Validators?" -- Shreya Shankar
#
# If you use LLMJudge to assess quality, how do you know the judge
# is actually right? A judge that always says "pass" is useless.
# A judge that disagrees with human experts is misleading.
#
# The solution: create a "meta-eval" where you have human-labeled
# ground truth for the JUDGE'S output, not just the agent's output.
#
# Process:
#   1. Run the agent on a set of cases
#   2. Have a human label each output as pass/fail
#   3. Run the LLMJudge on the same cases
#   4. Compare judge labels vs human labels
#   5. Compute agreement rate (Cohen's kappa or simple accuracy)
#
# If agreement is high, you can trust the judge for automated evals.
# If agreement is low, refine the rubric or switch judge models.


@dataclass
class HumanLabel:
    """A human-provided label for judge validation."""

    case_name: str
    agent_output: SecurityCategory
    expected_output: SecurityCategory
    human_judgment: bool  # True = human says agent output is acceptable
    human_note: str


# These represent a human expert reviewing the agent's actual outputs
# and deciding whether each classification is acceptable.
HUMAN_LABELS: list[HumanLabel] = [
    HumanLabel(
        case_name="clear_debt",
        agent_output=SecurityCategory.DEBT,
        expected_output=SecurityCategory.DEBT,
        human_judgment=True,
        human_note="Correct. Clear debt instrument.",
    ),
    HumanLabel(
        case_name="clear_safe",
        agent_output=SecurityCategory.SAFE,
        expected_output=SecurityCategory.SAFE,
        human_judgment=True,
        human_note="Correct. Unambiguous SAFE.",
    ),
    HumanLabel(
        case_name="convertible_note_as_debt",
        agent_output=SecurityCategory.DEBT,
        expected_output=SecurityCategory.CONVERTIBLE_NOTE,
        human_judgment=True,  # Human says: debt is defensible for a convertible note
        human_note="Acceptable. It IS a note with debt features. Convertible_note is more specific, but debt is not wrong.",
    ),
    HumanLabel(
        case_name="hybrid_as_convertible",
        agent_output=SecurityCategory.CONVERTIBLE_NOTE,
        expected_output=SecurityCategory.CONVERTIBLE_NOTE,
        human_judgment=True,
        human_note="Correct. Mandatory conversion makes this a convertible.",
    ),
    HumanLabel(
        case_name="safe_as_equity",
        agent_output=SecurityCategory.EQUITY,
        expected_output=SecurityCategory.SAFE,
        human_judgment=False,  # Human says: SAFE is NOT equity yet
        human_note="Wrong. SAFE converts to equity in the future, but it is not equity now.",
    ),
    HumanLabel(
        case_name="debt_as_equity",
        agent_output=SecurityCategory.EQUITY,
        expected_output=SecurityCategory.DEBT,
        human_judgment=False,  # Human says: clearly wrong
        human_note="Wrong. Secured notes with fixed interest are debt, not equity.",
    ),
    HumanLabel(
        case_name="revenue_share_as_other",
        agent_output=SecurityCategory.OTHER,
        expected_output=SecurityCategory.REVENUE_SHARE,
        human_judgment=False,  # Human says: revenue_share is the right category
        human_note="Wrong. Revenue participation is its own category, not 'other'.",
    ),
    HumanLabel(
        case_name="fund_as_real_estate",
        agent_output=SecurityCategory.REAL_ESTATE,
        expected_output=SecurityCategory.FUND_INTEREST,
        human_judgment=True,  # Human says: a real estate fund is real_estate
        human_note="Acceptable. The fund invests in real estate, so real_estate is defensible.",
    ),
]


@dataclass
class JudgeValidator(Evaluator[str, bool]):
    """Meta-evaluator that checks if the LLMJudge agrees with human labels.

    This evaluator is used to validate the judge itself, not the agent.
    The 'input' is the case description, and the 'output' is the judge's
    pass/fail decision. The 'expected_output' is the human label.

    Returns True (assertion) if judge agrees with human.
    """

    def evaluate(self, ctx: EvaluatorContext[str, bool]) -> EvaluatorOutput:
        if ctx.expected_output is None:
            return {}

        judge_agrees = ctx.output == ctx.expected_output
        return {
            "judge_agrees_with_human": judge_agrees,
            "alignment_label": "aligned" if judge_agrees else "misaligned",
        }


def compute_judge_alignment(
    judge_decisions: list[bool],
    human_decisions: list[bool],
) -> dict[str, float]:
    """Compute alignment metrics between judge and human labels.

    This is a simplified version. In production, you would use
    Cohen's kappa, F1 score, or other inter-rater reliability metrics.
    """
    assert len(judge_decisions) == len(human_decisions)

    n = len(judge_decisions)
    if n == 0:
        return {"agreement_rate": 0.0, "n_cases": 0}

    agreements = sum(1 for j, h in zip(judge_decisions, human_decisions) if j == h)
    agreement_rate = agreements / n

    # Breakdown
    true_positives = sum(1 for j, h in zip(judge_decisions, human_decisions) if j and h)
    true_negatives = sum(
        1 for j, h in zip(judge_decisions, human_decisions) if not j and not h
    )
    false_positives = sum(
        1 for j, h in zip(judge_decisions, human_decisions) if j and not h
    )
    false_negatives = sum(
        1 for j, h in zip(judge_decisions, human_decisions) if not j and h
    )

    return {
        "agreement_rate": agreement_rate,
        "n_cases": float(n),
        "true_positives": float(true_positives),
        "true_negatives": float(true_negatives),
        "false_positives": float(false_positives),
        "false_negatives": float(false_negatives),
    }


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 10: ADVANCED EVALS")
    print("LLMJudge, model comparison, serialization, judge validation")
    print("=" * 70)
    print()

    # -------------------------------------------------------------------------
    # Demo 1: LLMJudge evaluation
    # -------------------------------------------------------------------------
    print("--- Demo 1: LLMJudge Evaluation ---")
    print("Running classification with LLMJudge evaluators...")
    print("(This makes multiple LLM calls: agent + 2 judge evaluators per case)")
    print()

    report_with_judge = llm_judge_dataset.evaluate_sync(
        classify_security,
        name="llm_judge_eval",
        max_concurrency=2,
    )

    report_with_judge.print(
        include_output=True,
        include_expected_output=True,
        include_reasons=True,
    )
    print()

    # -------------------------------------------------------------------------
    # Demo 2: Model Comparison
    # -------------------------------------------------------------------------
    print("--- Demo 2: Model Comparison ---")
    print("Running same dataset with different models...")
    print()

    # Run with the default model (Sonnet)
    report_sonnet = comparison_dataset.evaluate_sync(
        classify_security,
        name="sonnet",
    )
    print("Sonnet results:")
    report_sonnet.print(include_output=True)
    print()

    # Override with a different model and run again
    # NOTE: This requires the model to be available. Using override()
    # to demonstrate the pattern. In production you would compare
    # against models you actually have access to.
    #
    # Uncomment below to compare against a different model:
    #
    # with classification_agent.override(model="openai:gpt-4o"):
    #     report_gpt = comparison_dataset.evaluate_sync(
    #         classify_security,
    #         name="gpt-4o",
    #     )
    #     print("GPT-4o results:")
    #     report_gpt.print(include_output=True)
    #     print()
    #
    #     # Side-by-side comparison using the diff view
    #     print("--- Diff: Sonnet vs GPT-4o ---")
    #     report_gpt.print(
    #         baseline=report_sonnet,
    #         include_output=True,
    #     )

    # Show the comparison pattern even without a second model
    print("  Model comparison pattern:")
    print("    with agent.override(model='openai:gpt-4o'):")
    print("        report_gpt = dataset.evaluate_sync(task, name='gpt-4o')")
    print()
    print("    # Diff view shows changes between runs:")
    print("    report_gpt.print(baseline=report_sonnet)")
    print()

    # Demonstrate self-comparison (same model, shows that diff works)
    print("  Self-comparison (same model, two runs):")
    report_sonnet_2 = comparison_dataset.evaluate_sync(
        classify_security,
        name="sonnet-run2",
    )

    # Print the diff between two runs of the same model
    # This shows variance in stochastic outputs
    report_sonnet_2.print(
        baseline=report_sonnet,
        include_output=True,
    )
    print()

    # -------------------------------------------------------------------------
    # Demo 3: Dataset Serialization
    # -------------------------------------------------------------------------
    demo_serialization()

    # -------------------------------------------------------------------------
    # Demo 4: Judge Validation (simulated)
    # -------------------------------------------------------------------------
    print("--- Demo 4: Validating the Judge ---")
    print("'Who Validates the Validators?' -- Shreya Shankar")
    print()
    print("In production, you would:")
    print("  1. Run the agent on cases and collect outputs")
    print("  2. Have a human label each output as acceptable/unacceptable")
    print("  3. Run the LLMJudge on the same outputs")
    print("  4. Compare judge vs human labels")
    print()
    print("Here we simulate with pre-labeled data:")
    print()

    # Simulate judge decisions for each human-labeled case
    # In a real workflow, these would come from running the LLMJudge
    # For demonstration, we simulate plausible judge decisions
    simulated_judge_decisions = [
        True,  # clear_debt: judge agrees with human (pass)
        True,  # clear_safe: judge agrees with human (pass)
        True,  # convertible_note_as_debt: judge says pass (human: pass)
        True,  # hybrid_as_convertible: judge says pass (human: pass)
        True,  # safe_as_equity: judge says pass (but human: FAIL) -- judge is wrong!
        False,  # debt_as_equity: judge says fail (human: fail) -- correct
        True,  # revenue_share_as_other: judge says pass (but human: FAIL) -- judge too lenient!
        True,  # fund_as_real_estate: judge says pass (human: pass)
    ]

    human_decisions = [label.human_judgment for label in HUMAN_LABELS]

    alignment = compute_judge_alignment(simulated_judge_decisions, human_decisions)

    print(f"  Judge-Human agreement rate: {alignment['agreement_rate']:.0%}")
    print(f"  Total cases: {int(alignment['n_cases'])}")
    print(f"  True positives  (both say pass): {int(alignment['true_positives'])}")
    print(f"  True negatives  (both say fail): {int(alignment['true_negatives'])}")
    print(
        f"  False positives (judge pass, human fail): {int(alignment['false_positives'])}"
    )
    print(
        f"  False negatives (judge fail, human pass): {int(alignment['false_negatives'])}"
    )
    print()

    if alignment["false_positives"] > 0:
        print("  INSIGHT: Judge has false positives -- it is too lenient.")
        print("  The judge said 'pass' for cases where a human said 'fail'.")
        print(
            "  Action: Tighten the rubric to be more specific about failure criteria."
        )
        print()
        print("  Cases where judge was too lenient:")
        for i, (label, judge_dec) in enumerate(
            zip(HUMAN_LABELS, simulated_judge_decisions)
        ):
            if judge_dec and not label.human_judgment:
                print(f"    - {label.case_name}")
                print(f"      Agent output: {label.agent_output.value}")
                print(f"      Expected: {label.expected_output.value}")
                print(f"      Human note: {label.human_note}")
        print()

    if alignment["false_negatives"] > 0:
        print("  INSIGHT: Judge has false negatives -- it is too strict.")
        print("  The judge said 'fail' for cases where a human said 'pass'.")
        print(
            "  Action: Loosen the rubric or add more nuance about acceptable answers."
        )
        print()

    print()
    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. LLMJudge evaluates output quality against a rubric")
    print("     - include_input=True gives the judge context")
    print("     - include_expected_output=True enables comparison")
    print("     - Use different rubrics for different quality dimensions")
    print()
    print("  2. Model comparison with agent.override():")
    print("     - Same dataset, different models, comparable results")
    print("     - report.print(baseline=other_report) for diff view")
    print("     - Essential for model selection decisions")
    print()
    print("  3. Dataset serialization to YAML:")
    print("     - dataset.to_file() / Dataset.from_file()")
    print("     - Version control your eval cases in git")
    print("     - Share across team, run in CI/CD")
    print()
    print("  4. Validate the judge (Shreya Shankar):")
    print("     - Compare LLMJudge decisions against human labels")
    print("     - Track agreement rate, false positives, false negatives")
    print("     - A too-lenient judge gives false confidence")
    print("     - A too-strict judge wastes engineering time on 'failures'")
    print("     - Iterate on rubrics until judge aligns with human judgment")
    print()
    print("Next: Capstone -- Full classification pipeline with everything integrated")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
