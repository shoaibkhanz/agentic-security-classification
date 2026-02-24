"""
Module 02: Structured Output, Union Types, and Output Validators
================================================================

In Module 01, you saw Agent[DepsType, OutputType] with simple types.
Now go deeper into output_type — the constraint that forces the LLM
to produce exactly the data structure your application needs.

Core ideas:
  - output_type=SomeModel forces the LLM to return valid JSON matching that model
  - Union output types (A | B) let the LLM choose a branch based on input
  - Output validators run AFTER parsing, can raise ModelRetry to force correction
  - Pydantic field constraints (min_length, ge/le) catch invalid data at parse time

Why this matters for securities:
  Offering memoranda are messy free-text documents. We need structured extraction
  that either succeeds cleanly (ParsedOffering) or honestly admits what's missing
  (InsufficientInfo). Output validators enforce domain rules the LLM might ignore.

Sections:
  1. Basic Structured Output
  2. Union Output Types for Branching
  3. Output Validators with ModelRetry
  4. Field Constraints with Annotated Types
  5. Exercise: Full Document Parser
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from pydantic import BaseModel, Field

from pydantic_ai import Agent, ModelRetry, RunContext

from shared.models import (
    ExemptionType,
    InsufficientInfo,
    ParsedOffering,
    SecuritySummary,
)


# =============================================================================
# Section 1: Basic Structured Output
# =============================================================================
# When you set output_type, pydantic-ai tells the LLM the exact JSON schema
# it must produce. The LLM's response is parsed and validated by Pydantic.
#
# Compare to Module 01:
#   - Module 01: output_type=str (LLM returns free text)
#   - Module 02: output_type=SecuritySummary (LLM MUST return matching JSON)
#
# Under the hood, pydantic-ai uses tool-calling: it registers a "final_result"
# tool whose schema matches SecuritySummary. The LLM "calls" that tool with
# the structured data, and pydantic-ai validates it.

summary_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=SecuritySummary,
    system_prompt=(
        "You are a securities analyst. Given a description of a private security, "
        "extract a structured summary. Be precise and factual."
    ),
)


async def demo_basic_structured_output() -> None:
    """Show that the LLM is constrained to return a SecuritySummary."""
    print("--- Section 1: Basic Structured Output ---\n")

    # The LLM must return a SecuritySummary — it cannot return free text.
    result = await summary_agent.run(
        "Meridian Growth Fund LP offers limited partnership interests in a "
        "diversified private equity fund managed by Meridian Capital Partners. "
        "The fund targets mid-market buyouts in technology and healthcare sectors. "
        "Minimum investment of $250,000. Accredited investors only. "
        "Offering amount: $75M under Reg D 506(c)."
    )

    # result.output is SecuritySummary, not str — fully typed
    summary: SecuritySummary = result.output
    print(f"Type returned: {type(summary).__name__}")
    print(f"  name: {summary.name}")
    print(f"  issuer: {summary.issuer}")
    print(f"  security_type: {summary.security_type}")
    print(f"  key_details: {summary.key_details}")
    print()

    # Key insight: If the LLM returns JSON that doesn't match SecuritySummary,
    # Pydantic raises a validation error. pydantic-ai catches it and asks the
    # LLM to try again (up to the retry limit). You never see malformed output.


# =============================================================================
# Section 2: Union Output Types for Branching
# =============================================================================
# Union types (A | B) are where structured output gets powerful.
# The LLM must choose ONE of the types based on the input. This creates
# branching logic without if/else in your code — the LLM decides.
#
# For securities: an offering document either has enough info to extract
# a ParsedOffering, or it doesn't and we get InsufficientInfo.
#
# pydantic-ai registers BOTH types as possible "final_result" tools.
# The LLM picks which one to call based on the input.

parser_agent = Agent(
    "anthropic:sonnet-4-5-20250929",
    # Union type: LLM chooses ParsedOffering OR InsufficientInfo
    output_type=ParsedOffering | InsufficientInfo,
    system_prompt=(
        "You are a securities document parser. Given an offering memorandum "
        "or description, extract structured information.\n\n"
        "If the document contains enough information to identify the issuer, "
        "security type, and exemption type, return a ParsedOffering.\n\n"
        "If critical information is missing, return InsufficientInfo with:\n"
        "  - missing_fields: what couldn't be extracted\n"
        "  - questions_to_ask: what you'd need to complete the extraction\n"
        "  - partial_extraction: whatever you could partially identify\n\n"
        "Be honest about what's missing. Do not guess at exemption types."
    ),
)


async def demo_union_output_types() -> None:
    """Show how union types let the LLM branch on data quality."""
    print("--- Section 2: Union Output Types for Branching ---\n")

    # Case 1: Complete document — LLM should return ParsedOffering
    complete_doc = (
        "OFFERING MEMORANDUM\n"
        "Issuer: Atlas Infrastructure Corp\n"
        "Security: Senior Secured Notes due 2027\n"
        "Offering Amount: $25,000,000\n"
        "Minimum Investment: $50,000\n"
        "Interest Rate: 8.5% per annum, paid quarterly\n"
        "Maturity: June 1, 2027\n"
        "Exemption: Regulation D, Rule 506(b)\n"
        "Notes are secured by the company's infrastructure asset portfolio."
    )

    result1 = await parser_agent.run(complete_doc)
    print(f"Complete document -> {type(result1.output).__name__}")
    if isinstance(result1.output, ParsedOffering):
        print(f"  issuer: {result1.output.issuer}")
        print(f"  security_type: {result1.output.security_type}")
        print(f"  exemption: {result1.output.exemption.value}")
        print(f"  min_investment: {result1.output.min_investment}")
        print(f"  key_terms: {result1.output.key_terms}")
    print()

    # Case 2: Vague document — LLM should return InsufficientInfo
    vague_doc = (
        "CONFIDENTIAL\n"
        "Zenith Partners - Special Purpose Vehicle\n"
        "Investment opportunity for qualified purchasers.\n"
        "Details available upon request.\n"
        "Contact: info@zenithpartners.example.com"
    )

    result2 = await parser_agent.run(vague_doc)
    print(f"Vague document -> {type(result2.output).__name__}")
    if isinstance(result2.output, InsufficientInfo):
        print(f"  missing_fields: {result2.output.missing_fields}")
        print(f"  questions_to_ask: {result2.output.questions_to_ask}")
        print(f"  partial_extraction: {result2.output.partial_extraction}")
    print()

    # Key insight: Your application code uses isinstance() to handle each branch.
    # The LLM made the decision; your code handles the result. No prompt parsing.


# =============================================================================
# Section 3: Output Validators with ModelRetry
# =============================================================================
# Output validators run AFTER Pydantic parsing succeeds. They enforce
# business rules that go beyond schema validation.
#
# Pattern:
#   1. LLM returns JSON
#   2. Pydantic parses and validates field types (Section 4)
#   3. Output validator runs your custom logic
#   4. If validator raises ModelRetry, the LLM tries again with the error message
#   5. This creates a feedback loop: LLM -> validate -> retry -> LLM -> validate
#
# For securities: we want to ensure the LLM doesn't take shortcuts like
# returning UNKNOWN for exemption type when the document clearly states it.

validated_parser = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=ParsedOffering | InsufficientInfo,
    system_prompt=(
        "You are a securities document parser specializing in private placements. "
        "Given an offering memorandum, extract structured information.\n\n"
        "IMPORTANT: You must identify the specific SEC exemption type from the "
        "document. Common exemptions include:\n"
        "  - Regulation D Rule 506(b): Private placement, no general solicitation\n"
        "  - Regulation D Rule 506(c): Allows general solicitation, accredited only\n"
        "  - Regulation A/A+: Mini-IPO, up to $75M\n"
        "  - Regulation CF: Crowdfunding, up to $5M\n"
        "  - Regulation S: Offshore transactions\n"
        "  - Section 4(a)(2): Statutory private placement exemption\n\n"
        "If the document mentions an exemption, you MUST identify it specifically. "
        "Only use UNKNOWN if the document truly provides no exemption information.\n\n"
        "If critical information is missing, return InsufficientInfo instead."
    ),
)


@validated_parser.output_validator
async def validate_parsed_offering(
    ctx: RunContext[None], output: ParsedOffering | InsufficientInfo
) -> ParsedOffering | InsufficientInfo:
    """
    Validate business rules that the schema alone can't enforce.

    This validator runs after Pydantic parsing succeeds. It checks domain-specific
    rules and raises ModelRetry to give the LLM a second chance.

    ModelRetry is the key mechanism: it sends the error message back to the LLM
    as a tool error, prompting it to correct its output. The LLM sees what went
    wrong and adjusts.
    """
    if isinstance(output, ParsedOffering):
        # Rule 1: If we got a ParsedOffering, the exemption should be identified.
        # The LLM sometimes defaults to UNKNOWN out of caution — push it to try harder.
        if output.exemption == ExemptionType.UNKNOWN:
            raise ModelRetry(
                "You returned a ParsedOffering but the exemption type is UNKNOWN. "
                "Re-read the document carefully. Look for mentions of 'Regulation D', "
                "'506(b)', '506(c)', 'Reg A', 'Reg CF', 'Reg S', or 'Section 4(a)(2)'. "
                "If you truly cannot determine the exemption, return InsufficientInfo instead."
            )

        # Rule 2: Security type should not be overly generic.
        generic_types = {"security", "investment", "instrument", "offering"}
        if output.security_type.lower().strip() in generic_types:
            raise ModelRetry(
                f"Security type '{output.security_type}' is too generic. "
                "Be more specific: e.g., 'senior secured notes', 'convertible note', "
                "'SAFE', 'preferred stock', 'limited partnership interest', etc."
            )

        # Rule 3: If min_investment is present, it should be positive.
        if output.min_investment is not None and output.min_investment <= 0:
            raise ModelRetry(
                f"min_investment must be positive, got {output.min_investment}. "
                "Check the document for the correct minimum investment amount."
            )

    elif isinstance(output, InsufficientInfo):
        # Rule 4: InsufficientInfo should actually have useful questions.
        if len(output.questions_to_ask) == 0:
            raise ModelRetry(
                "You returned InsufficientInfo but didn't suggest any questions. "
                "What would you need to know to complete the extraction? "
                "Suggest at least 2 specific questions."
            )

    return output


async def demo_output_validators() -> None:
    """Show how output validators catch domain errors and trigger retries."""
    print("--- Section 3: Output Validators with ModelRetry ---\n")

    # This document mentions Reg D 506(b) — the validator ensures the LLM catches it
    doc_with_exemption = (
        "PRIVATE PLACEMENT MEMORANDUM\n"
        "Catalyst Biotech Inc\n"
        "Convertible Promissory Notes\n"
        "Total Offering: $3,000,000\n"
        "Minimum Investment: $10,000\n"
        "Interest Rate: 6% per annum\n"
        "Maturity: 24 months from issuance\n"
        "Conversion: Auto-converts at Series A ($5M+ qualified financing)\n"
        "  - 25% discount to Series A price, OR\n"
        "  - $15M valuation cap (whichever is more favorable to holder)\n"
        "This offering is made pursuant to Regulation D, Rule 506(b). "
        "Not available via general solicitation."
    )

    result = await validated_parser.run(doc_with_exemption)
    print(f"Result type: {type(result.output).__name__}")
    if isinstance(result.output, ParsedOffering):
        print(f"  issuer: {result.output.issuer}")
        print(f"  security_type: {result.output.security_type}")
        print(f"  exemption: {result.output.exemption.value}")
        print(f"  min_investment: {result.output.min_investment}")
        print(f"  key_terms: {result.output.key_terms}")
    print()

    # The validator ensures exemption != UNKNOWN when the doc clearly states it.
    # If the LLM initially returned UNKNOWN, ModelRetry would force a correction.
    # You can check result.usage() to see if extra retries happened.
    print(f"  Token usage (retries add tokens): {result.usage()}")
    print()


# =============================================================================
# Section 4: Field Constraints with Annotated Types
# =============================================================================
# Pydantic field constraints validate data at PARSE time — before your output
# validator even runs. These catch structural problems immediately.
#
# Common constraints:
#   - min_length / max_length: string length bounds
#   - ge / le / gt / lt: numeric bounds (greater/equal, less/equal, etc.)
#   - pattern: regex matching
#   - Field(description=...): tells the LLM what the field means
#
# When a field constraint fails, pydantic-ai sends the validation error
# back to the LLM as a retry, just like ModelRetry.

# Custom model with tighter constraints than the shared ParsedOffering.
# This demonstrates how Annotated types add validation at the field level.


class StrictOfferingExtraction(BaseModel):
    """
    Tightly constrained offering extraction.

    Each field has explicit constraints that Pydantic enforces at parse time.
    If the LLM produces a value that violates a constraint, pydantic-ai
    automatically sends the validation error back and asks the LLM to fix it.
    """

    issuer_name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=200,
            description="Legal name of the issuing entity (not ticker or abbreviation)",
        ),
    ]

    security_type: Annotated[
        str,
        Field(
            min_length=3,
            max_length=100,
            description=(
                "Specific type of security: e.g., 'senior secured notes', "
                "'convertible promissory note', 'SAFE', 'preferred stock', "
                "'limited partnership interest'. Must not be generic terms "
                "like 'security' or 'investment'."
            ),
        ),
    ]

    offering_amount_usd: Annotated[
        float | None,
        Field(
            ge=0,
            le=10_000_000_000,  # $10B cap — sanity check
            description="Total offering amount in USD. None if not stated.",
        ),
    ]

    minimum_investment_usd: Annotated[
        float | None,
        Field(
            ge=100,  # Minimum $100 — below this is likely an error
            le=100_000_000,  # $100M cap
            description="Minimum investment amount in USD. None if not stated.",
        ),
    ]

    interest_rate_pct: Annotated[
        float | None,
        Field(
            ge=0.0,
            le=100.0,  # Percentage, not decimal
            description="Annual interest rate as percentage (e.g., 8.5 for 8.5%). None if not applicable.",
        ),
    ]

    exemption_type: ExemptionType = Field(
        description="SEC registration exemption. Use UNKNOWN only if document provides no exemption info."
    )

    risk_factors_mentioned: Annotated[
        int,
        Field(
            ge=0,
            le=50,
            description="Count of distinct risk factors mentioned in the document.",
        ),
    ]

    summary: Annotated[
        str,
        Field(
            min_length=20,
            max_length=500,
            description="Concise summary of the offering in 1-3 sentences.",
        ),
    ]


strict_parser = Agent(
    "anthropic:sonnet-4-5-20250929",
    output_type=StrictOfferingExtraction,
    system_prompt=(
        "You are a precise securities document extractor. "
        "Extract offering details exactly as constrained by the output schema. "
        "Pay attention to field constraints — they exist for data quality."
    ),
)


async def demo_field_constraints() -> None:
    """Show how Pydantic field constraints provide parse-time validation."""
    print("--- Section 4: Field Constraints with Annotated Types ---\n")

    doc = (
        "OFFERING MEMORANDUM - CONFIDENTIAL\n\n"
        "Pacific Heights Residences Fund\n"
        "Issuer: Pacific Heights Real Estate LLC\n\n"
        "Pacific Heights Residences Fund offers membership interests in a real "
        "estate investment vehicle targeting luxury multifamily properties in "
        "the San Francisco Bay Area.\n\n"
        "Offering Amount: $40,000,000\n"
        "Minimum Investment: $100,000\n"
        "Target IRR: 15-18%\n"
        "Hold Period: 5 years\n"
        "Exemption: Regulation D, Rule 506(c)\n"
        "Accredited investors only. General solicitation permitted.\n\n"
        "RISK FACTORS:\n"
        "1. Real estate market fluctuations\n"
        "2. Interest rate risk\n"
        "3. Illiquidity — 5 year lock-up\n"
        "4. Concentration risk — Bay Area only\n"
        "5. Construction and development delays\n"
        "6. Regulatory changes affecting real estate\n"
    )

    result = await strict_parser.run(doc)
    output = result.output

    print(f"Type: {type(output).__name__}")
    print(f"  issuer_name: {output.issuer_name!r}")
    print(f"  security_type: {output.security_type!r}")
    print(f"  offering_amount_usd: {output.offering_amount_usd}")
    print(f"  minimum_investment_usd: {output.minimum_investment_usd}")
    print(f"  interest_rate_pct: {output.interest_rate_pct}")
    print(f"  exemption_type: {output.exemption_type.value}")
    print(f"  risk_factors_mentioned: {output.risk_factors_mentioned}")
    print(f"  summary: {output.summary!r}")
    print()

    # Key insight: All of these constraints (min_length, ge, le) are enforced
    # by Pydantic at parse time. If the LLM returns offering_amount="-5000",
    # Pydantic rejects it, and pydantic-ai sends the error back for retry.
    # The LLM sees "Value error, ensure this value is greater than or equal to 0"
    # and corrects itself. You never see invalid data.


# =============================================================================
# Section 5: Exercise — Full Document Parser
# =============================================================================
# Combine everything: union types, output validators, and field constraints
# into a realistic securities document parser.
#
# This is what a production pipeline looks like:
#   1. Ingest raw offering memorandum text
#   2. Agent extracts ParsedOffering | InsufficientInfo
#   3. Output validator enforces business rules
#   4. Application routes to next step based on which type was returned


# Sample offering documents — realistic free-text memoranda
SAMPLE_OFFERINGS = {
    "novatech_safe": (
        "OFFERING NOTICE\n\n"
        "NovaTech AI Inc\n"
        "Simple Agreement for Future Equity (SAFE)\n\n"
        "NovaTech AI Inc is raising $5,000,000 via SAFE instruments to fund "
        "development of its enterprise AI platform.\n\n"
        "Terms:\n"
        "  - 20% discount to next priced round\n"
        "  - $20M valuation cap\n"
        "  - Y Combinator standard SAFE (post-money)\n"
        "  - Minimum investment: $25,000\n\n"
        "This offering is made under Regulation D, Rule 506(b). "
        "No general solicitation. Pre-existing relationship required.\n\n"
        "NovaTech AI is building foundational AI models for enterprise "
        "data analysis. Founded 2023, team of 12, based in San Francisco."
    ),
    "stellar_bonds": (
        "COMMUNITY SOLAR BOND OFFERING\n\n"
        "Stellar Energy Cooperative\n\n"
        "Stellar Energy Cooperative is offering community solar bonds to fund "
        "the installation of solar panels on public buildings across three counties.\n\n"
        "Bond Terms:\n"
        "  - 4.5% annual coupon\n"
        "  - 10-year maturity (September 2034)\n"
        "  - $1,000 minimum investment\n"
        "  - Total offering: $5,000,000\n\n"
        "This offering is made under Regulation A+ (Tier 2). "
        "Non-accredited investors are welcome to participate.\n\n"
        "Stellar Energy is a member-owned cooperative serving 15,000 households "
        "in the Pacific Northwest."
    ),
    "mystery_spv": (
        "CONFIDENTIAL — DO NOT DISTRIBUTE\n\n"
        "Opportunity Fund\n"
        "Premium Returns. Limited Availability.\n\n"
        "Join our exclusive investment vehicle. Minimum commitment required.\n"
        "Track record of strong performance.\n\n"
        "Contact us for full details.\n"
        "Email: invest@example.com"
    ),
    "riverview_revenue": (
        "INVESTMENT OPPORTUNITY\n\n"
        "Riverview SaaS Corp — Revenue Participation Agreement\n\n"
        "Participate in Riverview's growth! As an investor, you will receive "
        "a share of monthly recurring revenue until 2x your investment is "
        "returned, then 0.5% of revenue in perpetuity.\n\n"
        "This is not equity and not debt — it is a revenue-based instrument.\n\n"
        "Minimum investment: $5,000\n"
        "Total raise: $2,000,000\n\n"
        "Offered via Regulation Crowdfunding (Reg CF) on EquityPortal platform.\n\n"
        "Riverview SaaS Corp provides customer analytics software to mid-market "
        "retailers. $1.2M ARR, 140% net revenue retention, 85% gross margins."
    ),
}


async def demo_exercise_full_parser() -> None:
    """
    Exercise: Parse multiple offering documents and handle both branches.

    This demonstrates the full pipeline:
      text -> agent -> ParsedOffering | InsufficientInfo -> route accordingly
    """
    print("--- Section 5: Exercise — Full Document Parser ---\n")

    for name, doc_text in SAMPLE_OFFERINGS.items():
        print(f"Parsing: {name}")
        print(f"  Document length: {len(doc_text)} chars")

        result = await validated_parser.run(doc_text)
        output = result.output

        if isinstance(output, ParsedOffering):
            print("  -> ParsedOffering")
            print(f"     issuer: {output.issuer}")
            print(f"     security_type: {output.security_type}")
            print(f"     exemption: {output.exemption.value}")
            print(f"     min_investment: {output.min_investment}")
            print(f"     key_terms: {output.key_terms[:80]}...")
        elif isinstance(output, InsufficientInfo):
            print("  -> InsufficientInfo")
            print(f"     missing: {output.missing_fields}")
            print(f"     questions: {output.questions_to_ask[:2]}")
            if output.partial_extraction:
                print(f"     partial: {output.partial_extraction}")
        else:
            # This branch should never execute — Union is exhaustive.
            # But it demonstrates defensive programming with union types.
            print(f"  -> Unexpected type: {type(output).__name__}")

        print()


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    print("=" * 70)
    print("MODULE 02: STRUCTURED OUTPUT, UNION TYPES, AND OUTPUT VALIDATORS")
    print("Constraining LLM output to typed Pydantic models")
    print("=" * 70)
    print()

    # Section 1: Basic structured output
    await demo_basic_structured_output()

    # Section 2: Union types — LLM chooses the branch
    await demo_union_output_types()

    # Section 3: Output validators — domain rules with ModelRetry
    await demo_output_validators()

    # Section 4: Field constraints — parse-time validation
    await demo_field_constraints()

    # Section 5: Exercise — full document parser pipeline
    await demo_exercise_full_parser()

    print("=" * 70)
    print("KEY TAKEAWAYS:")
    print("  1. output_type=Model forces the LLM to return valid JSON")
    print("  2. Union types (A | B) let the LLM branch on input quality")
    print("  3. isinstance() in your code handles each branch (no parsing)")
    print("  4. @output_validator + ModelRetry = feedback loop for corrections")
    print("  5. Field constraints (ge, le, min_length) catch errors at parse time")
    print("  6. All validation errors are sent back to the LLM for self-correction")
    print()
    print("PATTERN: Text -> Agent -> Union[Good, Bad] -> Route")
    print("  This pattern replaces fragile regex/heuristic extraction pipelines.")
    print()
    print("Next: Module 03 — Tools, context injection, and retry strategies")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
