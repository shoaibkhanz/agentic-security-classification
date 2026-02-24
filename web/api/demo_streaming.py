"""
Demo SSE streaming — simulates the full classification pipeline
without requiring a live LLM API key.

Produces realistic investigation events that mirror what the real
pipeline emits, with timed delays to simulate thinking/tool execution.
This is invaluable for:
  1. Tutorial students who don't have API credits
  2. UI development and testing
  3. Demos and presentations

The demo scripts are keyed by security type hint. Each script defines
the full investigation timeline: which tools to call, what to find,
how confidence changes, and the final classification.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator
from typing import Any

from web.api.schemas import ClassifyRequest, StreamEvent


# ---------------------------------------------------------------------------
# Pre-scripted investigation scenarios
# ---------------------------------------------------------------------------
# Each scenario is a list of "steps" the agent takes. Each step produces
# one or more SSE events (node_start, confidence_update, evidence_found).
# The final result event is generated from the scenario's result_data.


def _serialize_event(event: StreamEvent) -> str:
    """Serialize a StreamEvent to JSON for SSE.

    Returns plain JSON — sse-starlette's EventSourceResponse adds
    the 'data:' prefix and newlines automatically.
    """
    return json.dumps(event.model_dump(mode="json"))


def _extract_issuer(description: str) -> str:
    """Try to extract the issuer/company name from description."""
    # Look for "X Corp", "X Inc", "X LLC" patterns
    match = re.search(
        r"([A-Z][A-Za-z\s]+(?:Corp|Inc|LLC|LP|Ltd|Partners|Capital|Fund|Trust))",
        description,
    )
    if match:
        return match.group(1).strip()
    # Fall back to first few capitalized words
    words = description.split()[:4]
    return " ".join(w for w in words if w[0:1].isupper())


def _build_debt_scenario(issuer: str, desc: str) -> dict[str, Any]:
    """Build investigation steps for a debt security (notes, bonds)."""
    return {
        "steps": [
            # Step 1: Initial Assessment
            {
                "node": "InitialAssessment",
                "stage": "I",
                "stage_name": "Initial Assessment",
                "delay": 0.8,
                "question_number": 0,
            },
            # Step 2: confidence after initial assessment
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.5,
                "question_number": 1,
                "confidence": {
                    "score": 0.35,
                    "top_category": "debt",
                    "runner_up": "convertible_note",
                    "uncertainty_reasons": [
                        "Need to verify if notes have conversion features",
                        "Haven't confirmed regulatory filing status",
                    ],
                    "step": 1,
                    "confidence_delta": 0.35,
                    "confidence_delta_pct": 35,
                },
            },
            # Step 3: Plan → search database
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.6,
                "question_number": 1,
                "current_category": "debt",
            },
            # Step 4: GatherInfo — database query
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.2,
                "question_number": 2,
                "current_category": "debt",
                "action_type": "query_db",
                "action_detail": f"Search internal securities database for {issuer} to find existing records, prior classifications, and offering history",
                "tool_name": "Securities Database Query",
                "data_source": "Internal Database",
                "expected_info_gain": "Determine if this issuer has prior offerings and what structure they used",
            },
            # Evidence from database
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 2,
                "evidence": {
                    "finding": f"Found {issuer} in database: Infrastructure holding company, 3 prior debt offerings since 2021. All structured as senior secured notes with fixed coupon rates.",
                    "source_type": "database",
                    "source_detail": f"Internal DB record: {issuer} (CIK-like ID: SEC-2024-08832)",
                    "content": f"{issuer} — Registered issuer. Sector: Infrastructure. Prior offerings: 2021 Series A Notes ($15M, 7.2%), 2022 Series B Notes ($20M, 7.8%), 2023 Series C Notes ($22M, 8.1%). All senior secured, fixed rate, quarterly coupon.",
                    "relevance": "high",
                    "tool_name": "Securities Database Query",
                    "data_source": "Internal Database",
                },
            },
            # Step 5: Confidence update after DB
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.5,
                "question_number": 2,
                "confidence": {
                    "score": 0.62,
                    "top_category": "debt",
                    "runner_up": "convertible_note",
                    "uncertainty_reasons": [
                        "Need to verify current offering terms match debt structure",
                        "Should check SEC filings for regulatory classification",
                    ],
                    "step": 2,
                    "confidence_delta": 0.27,
                    "confidence_delta_pct": 27,
                },
            },
            # Step 6: Plan → search SEC
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.5,
                "question_number": 2,
                "current_category": "debt",
            },
            # Step 7: GatherInfo — SEC EDGAR search
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.5,
                "question_number": 3,
                "current_category": "debt",
                "action_type": "search_sec",
                "action_detail": f"Search SEC EDGAR for {issuer} Form D filings to confirm offering type, exemption status, and whether securities are registered or exempt",
                "tool_name": "SEC EDGAR Data Parser",
                "data_source": "SEC EDGAR",
                "expected_info_gain": "Confirm regulatory classification and exemption type (Reg D 506(b) vs 506(c))",
            },
            # Evidence from SEC
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 3,
                "evidence": {
                    "finding": f"{issuer} filed Form D with SEC under Regulation D Rule 506(b). Offering: $25M senior secured notes. No conversion features disclosed. Accredited investors only.",
                    "source_type": "sec_filing",
                    "source_detail": f"SEC EDGAR Form D — {issuer} (Filed 2024-01-15)",
                    "content": f"Form D filing: {issuer}. Federal exemption: Rule 506(b) of Regulation D. Type of securities: Debt — Senior Secured Notes. Total offering amount: $25,000,000. Minimum investment: $100,000. Sales compensation: None. Duration: 3 years. Interest: 8.5% fixed, quarterly.",
                    "relevance": "high",
                    "tool_name": "SEC EDGAR Data Parser",
                    "data_source": "SEC EDGAR",
                },
            },
            # Step 8: Confidence update after SEC
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.5,
                "question_number": 3,
                "confidence": {
                    "score": 0.85,
                    "top_category": "debt",
                    "runner_up": None,
                    "uncertainty_reasons": [
                        "Confirm no embedded derivatives or conversion features",
                    ],
                    "step": 3,
                    "confidence_delta": 0.23,
                    "confidence_delta_pct": 23,
                },
            },
            # Step 9: Plan → web search for final confirmation
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.4,
                "question_number": 3,
                "current_category": "debt",
            },
            # Step 10: GatherInfo — web search
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.0,
                "question_number": 4,
                "current_category": "debt",
                "action_type": "search_web",
                "action_detail": f"Search web for {issuer} 2024 senior secured notes offering memorandum to verify collateral structure and confirm no convertible features",
                "tool_name": "Web Intelligence Search",
                "data_source": "Public Web",
                "expected_info_gain": "Verify collateral backing and confirm straight debt without conversion/equity features",
            },
            # Evidence from web
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 4,
                "evidence": {
                    "finding": f"{issuer} 2024 Notes are secured by the company's infrastructure asset portfolio valued at $45M. No conversion features, no equity warrants. Standard debt covenants apply.",
                    "source_type": "web_search",
                    "source_detail": f"{issuer} Offering Memorandum (via private placement portal)",
                    "content": f"Offering Summary: {issuer} Series D Senior Secured Notes. Principal: $25M. Security: First-priority lien on infrastructure assets (appraised value: $45M, LTV: 55.6%). Covenants: Debt service coverage ratio ≥ 1.5x, no additional senior debt without consent. No conversion rights. No detachable warrants. No equity participation.",
                    "relevance": "high",
                    "tool_name": "Web Intelligence Search",
                    "data_source": "Public Web",
                },
            },
            # Step 11: Final confidence
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 4,
                "confidence": {
                    "score": 0.95,
                    "top_category": "debt",
                    "runner_up": None,
                    "uncertainty_reasons": [],
                    "step": 4,
                    "confidence_delta": 0.10,
                    "confidence_delta_pct": 10,
                },
            },
            # Step 12: Classify
            {
                "node": "Classify",
                "stage": "V",
                "stage_name": "Classification",
                "delay": 0.8,
                "question_number": 4,
                "current_category": "debt",
            },
            # Step 13: Verify
            {
                "node": "Verify",
                "stage": "VI",
                "stage_name": "Verification",
                "delay": 0.6,
                "question_number": 4,
                "current_category": "debt",
            },
        ],
        "result": {
            "category": "debt",
            "confidence": 0.95,
            "reasoning": [
                {
                    "step": 1,
                    "evidence": f"{issuer} has history of senior secured note offerings",
                    "source": "database",
                    "inference": "Established pattern of straight debt issuance supports debt classification",
                    "confidence_delta": 0.27,
                },
                {
                    "step": 2,
                    "evidence": "Form D filed under Reg D 506(b) for senior secured notes",
                    "source": "sec_filing",
                    "inference": "SEC filing confirms debt structure with no conversion features",
                    "confidence_delta": 0.23,
                },
                {
                    "step": 3,
                    "evidence": "Offering memorandum confirms secured debt with no equity participation",
                    "source": "web_search",
                    "inference": "Collateralized debt with standard covenants, no hybrid features",
                    "confidence_delta": 0.10,
                },
            ],
            "evidence_sources": [
                {
                    "source_type": "database",
                    "source_detail": f"Internal DB: {issuer}",
                    "content": "3 prior debt offerings, all senior secured notes",
                },
                {
                    "source_type": "sec_filing",
                    "source_detail": f"SEC EDGAR Form D — {issuer}",
                    "content": "Reg D 506(b), $25M senior secured notes, accredited investors only",
                },
                {
                    "source_type": "web_search",
                    "source_detail": f"{issuer} Offering Memorandum",
                    "content": "First-priority lien on infrastructure assets, no conversion rights",
                },
            ],
            "questions_asked": 4,
            "alternative_classifications": [
                {
                    "category": "convertible_note",
                    "confidence": 0.03,
                    "reasoning": "Initially considered due to structured note format, but no conversion features found",
                },
            ],
            "summary": f"{issuer}'s $25M offering is classified as Debt Securities (senior secured notes). The notes bear 8.5% fixed interest, are secured by infrastructure assets, and have no conversion or equity participation features. Filed under Reg D 506(b) for accredited investors.",
            "prior_category": None,
            "needs_operator_review": True,
            "uncertainty_reasons": [],
            "audit_comment": "database: Established pattern of straight debt issuance. sec_filing: SEC filing confirms debt structure. web_search: Collateralized debt with standard covenants",
        },
    }


def _build_safe_scenario(issuer: str, desc: str) -> dict[str, Any]:
    """Build investigation steps for a SAFE instrument."""
    return {
        "steps": [
            {
                "node": "InitialAssessment",
                "stage": "I",
                "stage_name": "Initial Assessment",
                "delay": 0.7,
                "question_number": 0,
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 1,
                "confidence": {
                    "score": 0.45,
                    "top_category": "safe",
                    "runner_up": "convertible_note",
                    "uncertainty_reasons": [
                        "SAFE vs convertible note distinction requires verification",
                        "Need to confirm Y Combinator standard terms",
                    ],
                    "step": 1,
                    "confidence_delta": 0.45,
                    "confidence_delta_pct": 45,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.5,
                "question_number": 1,
                "current_category": "safe",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.0,
                "question_number": 2,
                "current_category": "safe",
                "action_type": "query_db",
                "action_detail": f"Query securities database for {issuer} to check for prior SAFE rounds and Y Combinator affiliation",
                "tool_name": "Securities Database Query",
                "data_source": "Internal Database",
                "expected_info_gain": "Verify if issuer has history of SAFE instruments vs convertible notes",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 2,
                "evidence": {
                    "finding": f"{issuer} is a Y Combinator W24 batch company. First recorded fundraise — no prior SAFE or convertible note history in database.",
                    "source_type": "database",
                    "source_detail": f"Internal DB: {issuer} (YC W24)",
                    "content": f"{issuer} — AI startup, Y Combinator Winter 2024 batch. Sector: Artificial Intelligence / Machine Learning. No prior fundraising rounds recorded. Founded 2023.",
                    "relevance": "medium",
                    "tool_name": "Securities Database Query",
                    "data_source": "Internal Database",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 2,
                "confidence": {
                    "score": 0.60,
                    "top_category": "safe",
                    "runner_up": "convertible_note",
                    "uncertainty_reasons": [
                        "Confirm SAFE vs convertible note — description says SAFE but need term sheet verification",
                    ],
                    "step": 2,
                    "confidence_delta": 0.15,
                    "confidence_delta_pct": 15,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.4,
                "question_number": 2,
                "current_category": "safe",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.2,
                "question_number": 3,
                "current_category": "safe",
                "action_type": "search_web",
                "action_detail": f"Search web for {issuer} SAFE round details — verify Y Combinator standard SAFE terms, discount rate, and valuation cap",
                "tool_name": "Web Intelligence Search",
                "data_source": "Public Web",
                "expected_info_gain": "Confirm this is a standard YC SAFE (not a convertible note disguised as SAFE)",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 3,
                "evidence": {
                    "finding": f"{issuer} is using the standard Y Combinator post-money SAFE. 20% discount to next priced round, $20M valuation cap. No interest accrual, no maturity date — confirming SAFE (not convertible note).",
                    "source_type": "web_search",
                    "source_detail": f"AngelList listing — {issuer} SAFE Round",
                    "content": "Instrument: Simple Agreement for Future Equity (SAFE). Standard: Y Combinator post-money SAFE (2023 template). Discount: 20%. Valuation cap: $20,000,000. No interest rate. No maturity date. No repayment obligation. Converts to preferred stock at next priced round ≥$1M.",
                    "relevance": "high",
                    "tool_name": "Web Intelligence Search",
                    "data_source": "Public Web",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 3,
                "confidence": {
                    "score": 0.92,
                    "top_category": "safe",
                    "runner_up": None,
                    "uncertainty_reasons": [],
                    "step": 3,
                    "confidence_delta": 0.32,
                    "confidence_delta_pct": 32,
                },
            },
            {
                "node": "Classify",
                "stage": "V",
                "stage_name": "Classification",
                "delay": 0.7,
                "question_number": 3,
                "current_category": "safe",
            },
            {
                "node": "Verify",
                "stage": "VI",
                "stage_name": "Verification",
                "delay": 0.5,
                "question_number": 3,
                "current_category": "safe",
            },
        ],
        "result": {
            "category": "safe",
            "confidence": 0.92,
            "reasoning": [
                {
                    "step": 1,
                    "evidence": f"{issuer} is a YC W24 company raising first round",
                    "source": "database",
                    "inference": "Early-stage YC company consistent with SAFE usage pattern",
                    "confidence_delta": 0.15,
                },
                {
                    "step": 2,
                    "evidence": "Standard YC post-money SAFE terms — no interest, no maturity",
                    "source": "web_search",
                    "inference": "Key distinction from convertible notes: no interest accrual and no maturity date",
                    "confidence_delta": 0.32,
                },
            ],
            "evidence_sources": [
                {
                    "source_type": "database",
                    "source_detail": f"Internal DB: {issuer}",
                    "content": "YC W24 batch company, first fundraise",
                },
                {
                    "source_type": "web_search",
                    "source_detail": f"AngelList — {issuer}",
                    "content": "Standard YC post-money SAFE, 20% discount, $20M cap",
                },
            ],
            "questions_asked": 3,
            "alternative_classifications": [
                {
                    "category": "convertible_note",
                    "confidence": 0.05,
                    "reasoning": "Considered due to convertible nature, but SAFE lacks interest/maturity features of convertible notes",
                },
            ],
            "summary": f"{issuer}'s $5M raise uses a standard Y Combinator post-money SAFE with 20% discount and $20M valuation cap. Classified as SAFE Instrument — distinct from convertible notes due to absence of interest accrual and maturity date.",
            "prior_category": None,
            "needs_operator_review": True,
            "uncertainty_reasons": [],
            "audit_comment": "database: YC W24 company pattern supports SAFE usage. web_search: Standard YC SAFE terms confirmed, no interest or maturity",
        },
    }


def _build_generic_scenario(issuer: str, desc: str) -> dict[str, Any]:
    """Fallback scenario for any security type — runs a full investigation."""
    return {
        "steps": [
            {
                "node": "InitialAssessment",
                "stage": "I",
                "stage_name": "Initial Assessment",
                "delay": 0.8,
                "question_number": 0,
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.5,
                "question_number": 1,
                "confidence": {
                    "score": 0.25,
                    "top_category": "other",
                    "runner_up": "equity",
                    "uncertainty_reasons": [
                        "Insufficient information — need to research the issuer",
                        "Security structure unclear from description alone",
                    ],
                    "step": 1,
                    "confidence_delta": 0.25,
                    "confidence_delta_pct": 25,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.5,
                "question_number": 1,
                "current_category": "other",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.2,
                "question_number": 2,
                "current_category": "other",
                "action_type": "query_db",
                "action_detail": f"Search internal securities database for {issuer} to find prior classification records and offering history",
                "tool_name": "Securities Database Query",
                "data_source": "Internal Database",
                "expected_info_gain": "Find existing records to establish issuer profile and prior security types",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 2,
                "evidence": {
                    "finding": f"Limited records found for {issuer}. No prior classifications in database. New issuer requiring full investigation.",
                    "source_type": "database",
                    "source_detail": f"Internal DB search: {issuer}",
                    "content": f"No matching records for {issuer}. Searched by name, issuer aliases, and CIK number. Recommend SEC EDGAR and web search for more information.",
                    "relevance": "low",
                    "tool_name": "Securities Database Query",
                    "data_source": "Internal Database",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 2,
                "confidence": {
                    "score": 0.30,
                    "top_category": "other",
                    "runner_up": "equity",
                    "uncertainty_reasons": [
                        "No database records — need SEC and web research",
                        "Cannot determine security type without more data",
                    ],
                    "step": 2,
                    "confidence_delta": 0.05,
                    "confidence_delta_pct": 5,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.4,
                "question_number": 2,
                "current_category": "other",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.5,
                "question_number": 3,
                "current_category": "other",
                "action_type": "search_sec",
                "action_detail": f"Search SEC EDGAR for {issuer} filings including Form D, S-1, 10-K to determine regulatory status and offering type",
                "tool_name": "SEC EDGAR Data Parser",
                "data_source": "SEC EDGAR",
                "expected_info_gain": "Determine regulatory filing status, offering exemption type, and security structure",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 3,
                "evidence": {
                    "finding": f"Found SEC filings for {issuer}. Form D filed under Regulation D. Offering details provide key structural information for classification.",
                    "source_type": "sec_filing",
                    "source_detail": f"SEC EDGAR — {issuer} Form D",
                    "content": f"SEC filing located for {issuer}. Type: Form D (Notice of Exempt Offering). Regulatory exemption: Rule 506. Additional details available from offering memorandum.",
                    "relevance": "high",
                    "tool_name": "SEC EDGAR Data Parser",
                    "data_source": "SEC EDGAR",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 3,
                "confidence": {
                    "score": 0.65,
                    "top_category": "other",
                    "runner_up": None,
                    "uncertainty_reasons": [
                        "Need offering memorandum for final structural determination",
                    ],
                    "step": 3,
                    "confidence_delta": 0.35,
                    "confidence_delta_pct": 35,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.4,
                "question_number": 3,
                "current_category": "other",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.0,
                "question_number": 4,
                "current_category": "other",
                "action_type": "search_web",
                "action_detail": f"Search web for {issuer} offering details, term sheet, and structure to finalize classification",
                "tool_name": "Web Intelligence Search",
                "data_source": "Public Web",
                "expected_info_gain": "Get final structural details to complete the classification",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 4,
                "evidence": {
                    "finding": f"Found detailed offering information for {issuer}. Structure and terms are consistent with description. Sufficient data for classification.",
                    "source_type": "web_search",
                    "source_detail": f"{issuer} offering details (web)",
                    "content": f"Offering details confirmed for {issuer}. Terms match the provided description. Classification can proceed with available evidence.",
                    "relevance": "high",
                    "tool_name": "Web Intelligence Search",
                    "data_source": "Public Web",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 4,
                "confidence": {
                    "score": 0.88,
                    "top_category": "other",
                    "runner_up": None,
                    "uncertainty_reasons": [],
                    "step": 4,
                    "confidence_delta": 0.23,
                    "confidence_delta_pct": 23,
                },
            },
            {
                "node": "Classify",
                "stage": "V",
                "stage_name": "Classification",
                "delay": 0.7,
                "question_number": 4,
                "current_category": "other",
            },
            {
                "node": "Verify",
                "stage": "VI",
                "stage_name": "Verification",
                "delay": 0.5,
                "question_number": 4,
                "current_category": "other",
            },
        ],
        "result": {
            "category": "other",
            "confidence": 0.88,
            "reasoning": [
                {
                    "step": 1,
                    "evidence": "No prior records in internal database",
                    "source": "database",
                    "inference": "New issuer requiring full external research",
                    "confidence_delta": 0.05,
                },
                {
                    "step": 2,
                    "evidence": f"SEC EDGAR Form D filing found for {issuer}",
                    "source": "sec_filing",
                    "inference": "Regulatory filing confirms exempt offering structure",
                    "confidence_delta": 0.35,
                },
                {
                    "step": 3,
                    "evidence": "Web search confirms offering structure details",
                    "source": "web_search",
                    "inference": "Terms consistent with described security type",
                    "confidence_delta": 0.23,
                },
            ],
            "evidence_sources": [
                {
                    "source_type": "database",
                    "source_detail": f"Internal DB: {issuer}",
                    "content": "No prior records found",
                },
                {
                    "source_type": "sec_filing",
                    "source_detail": f"SEC EDGAR — {issuer}",
                    "content": "Form D under Reg D Rule 506",
                },
                {
                    "source_type": "web_search",
                    "source_detail": f"{issuer} offering details",
                    "content": "Offering structure and terms confirmed",
                },
            ],
            "questions_asked": 4,
            "alternative_classifications": [],
            "summary": f"Classification of {issuer} offering based on SEC filings and web research. Confidence: 88%.",
            "prior_category": None,
            "needs_operator_review": True,
            "uncertainty_reasons": [],
            "audit_comment": "database: New issuer, no priors. sec_filing: Form D confirms exempt offering. web_search: Structural details verified",
        },
    }


def _build_convertible_note_scenario(issuer: str, desc: str) -> dict[str, Any]:
    """Build investigation steps for a convertible note."""
    return {
        "steps": [
            {
                "node": "InitialAssessment",
                "stage": "I",
                "stage_name": "Initial Assessment",
                "delay": 0.7,
                "question_number": 0,
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 1,
                "confidence": {
                    "score": 0.40,
                    "top_category": "convertible_note",
                    "runner_up": "debt",
                    "uncertainty_reasons": [
                        "Must distinguish from straight debt — verify conversion mechanics",
                        "Need to confirm auto-conversion trigger and pricing terms",
                    ],
                    "step": 1,
                    "confidence_delta": 0.40,
                    "confidence_delta_pct": 40,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.5,
                "question_number": 1,
                "current_category": "convertible_note",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.1,
                "question_number": 2,
                "current_category": "convertible_note",
                "action_type": "query_db",
                "action_detail": f"Search securities database for {issuer} to check for prior fundraising rounds and note conversion history",
                "tool_name": "Securities Database Query",
                "data_source": "Internal Database",
                "expected_info_gain": "Determine if issuer has prior convertible instruments and typical conversion terms",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 2,
                "evidence": {
                    "finding": f"Found {issuer} in database: Biotech startup, pre-Series A stage. No prior convertible notes recorded but company profile matches typical convertible note issuer pattern.",
                    "source_type": "database",
                    "source_detail": f"Internal DB: {issuer}",
                    "content": f"{issuer} — Biotech company, pre-Series A. Founded 2022. Sector: Biotechnology/Drug Development. No prior recorded fundraising. Company size suggests seed/pre-A stage consistent with convertible note usage.",
                    "relevance": "medium",
                    "tool_name": "Securities Database Query",
                    "data_source": "Internal Database",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 2,
                "confidence": {
                    "score": 0.55,
                    "top_category": "convertible_note",
                    "runner_up": "safe",
                    "uncertainty_reasons": [
                        "Convertible note vs SAFE — need to verify interest rate and maturity date",
                    ],
                    "step": 2,
                    "confidence_delta": 0.15,
                    "confidence_delta_pct": 15,
                },
            },
            {
                "node": "PlanNextAction",
                "stage": "IV",
                "stage_name": "Action Planning",
                "delay": 0.4,
                "question_number": 2,
                "current_category": "convertible_note",
            },
            {
                "node": "GatherInfo",
                "stage": "II",
                "stage_name": "Research & Data Gathering",
                "delay": 1.3,
                "question_number": 3,
                "current_category": "convertible_note",
                "action_type": "search_web",
                "action_detail": f"Search web for {issuer} convertible note terms to verify interest rate, maturity date, and auto-conversion triggers — key features that distinguish from SAFE instruments",
                "tool_name": "Web Intelligence Search",
                "data_source": "Public Web",
                "expected_info_gain": "Confirm presence of interest rate and maturity date (absent in SAFEs) to distinguish instrument type",
            },
            {
                "type": "evidence",
                "node": "GatherInfo",
                "delay": 0.3,
                "question_number": 3,
                "evidence": {
                    "finding": f"{issuer} convertible note has 6% annual interest and maturity date — both features absent in SAFE instruments. Auto-converts at qualified financing of $5M+. Discount rate: 25%.",
                    "source_type": "web_search",
                    "source_detail": f"{issuer} term sheet (via startup data platform)",
                    "content": "Instrument: Convertible Promissory Note. Interest rate: 6% per annum. Maturity: 24 months from issuance. Auto-conversion: At qualified financing ≥$5M. Conversion price: Lesser of (a) 25% discount to next round price, or (b) price based on $15M valuation cap. These terms confirm convertible note structure (interest + maturity = NOT a SAFE).",
                    "relevance": "high",
                    "tool_name": "Web Intelligence Search",
                    "data_source": "Public Web",
                },
            },
            {
                "type": "confidence",
                "node": "AssessConfidence",
                "stage": "III",
                "stage_name": "Confidence Assessment",
                "delay": 0.4,
                "question_number": 3,
                "confidence": {
                    "score": 0.93,
                    "top_category": "convertible_note",
                    "runner_up": None,
                    "uncertainty_reasons": [],
                    "step": 3,
                    "confidence_delta": 0.38,
                    "confidence_delta_pct": 38,
                },
            },
            {
                "node": "Classify",
                "stage": "V",
                "stage_name": "Classification",
                "delay": 0.7,
                "question_number": 3,
                "current_category": "convertible_note",
            },
            {
                "node": "Verify",
                "stage": "VI",
                "stage_name": "Verification",
                "delay": 0.5,
                "question_number": 3,
                "current_category": "convertible_note",
            },
        ],
        "result": {
            "category": "convertible_note",
            "confidence": 0.93,
            "reasoning": [
                {
                    "step": 1,
                    "evidence": f"{issuer} profile matches convertible note issuer pattern",
                    "source": "database",
                    "inference": "Pre-Series A biotech — typical stage for convertible note financing",
                    "confidence_delta": 0.15,
                },
                {
                    "step": 2,
                    "evidence": "6% interest rate and 24-month maturity confirm convertible note (not SAFE)",
                    "source": "web_search",
                    "inference": "Interest accrual and maturity date are definitive convertible note features absent in SAFEs",
                    "confidence_delta": 0.38,
                },
            ],
            "evidence_sources": [
                {
                    "source_type": "database",
                    "source_detail": f"Internal DB: {issuer}",
                    "content": "Pre-Series A biotech company",
                },
                {
                    "source_type": "web_search",
                    "source_detail": f"{issuer} term sheet",
                    "content": "6% interest, 24mo maturity, auto-converts at $5M+ qualified financing, 25% discount / $15M cap",
                },
            ],
            "questions_asked": 3,
            "alternative_classifications": [
                {
                    "category": "safe",
                    "confidence": 0.04,
                    "reasoning": "Initially considered but ruled out — SAFEs lack interest rate and maturity date",
                },
                {
                    "category": "debt",
                    "confidence": 0.02,
                    "reasoning": "Has debt-like features (interest) but conversion mechanism makes it a hybrid instrument",
                },
            ],
            "summary": f"{issuer}'s convertible promissory note with 6% interest and auto-conversion at qualified financing is classified as Convertible Note. Distinguished from SAFE by presence of interest accrual and maturity date.",
            "prior_category": None,
            "needs_operator_review": True,
            "uncertainty_reasons": [],
            "audit_comment": "database: Issuer profile matches convertible note pattern. web_search: Interest rate and maturity date confirm convertible note classification",
        },
    }


# Map keywords in the description to scenario builders
_SCENARIO_KEYWORDS: list[tuple[list[str], Any]] = [
    (
        ["senior secured", "notes", "bond", "coupon", "fixed rate", "interest rate"],
        _build_debt_scenario,
    ),
    (
        ["safe", "simple agreement for future equity", "valuation cap"],
        _build_safe_scenario,
    ),
    (
        ["convertible", "auto-convert", "conversion", "promissory note"],
        _build_convertible_note_scenario,
    ),
]


def _pick_scenario(desc: str) -> Any:
    """Pick the best scenario builder based on keywords in the description."""
    desc_lower = desc.lower()
    for keywords, builder in _SCENARIO_KEYWORDS:
        if any(kw in desc_lower for kw in keywords):
            return builder
    return _build_generic_scenario


# ---------------------------------------------------------------------------
# Main demo streaming function
# ---------------------------------------------------------------------------


async def stream_demo_classification(
    request: ClassifyRequest,
) -> AsyncGenerator[str, None]:
    """
    Simulate a full classification pipeline with realistic SSE events.

    Produces the same event types as the real pipeline (node_start,
    confidence_update, evidence_found, result) with appropriate timing
    delays to simulate LLM thinking and tool execution.
    """
    description = request.description
    issuer = _extract_issuer(description)
    scenario_builder = _pick_scenario(description)
    scenario = scenario_builder(issuer, description)

    elapsed = 0.0

    for step in scenario["steps"]:
        # Simulate processing delay
        delay = step.get("delay", 0.5)
        await asyncio.sleep(delay)
        elapsed += delay

        step_type = step.get("type")

        if step_type == "confidence":
            # Emit confidence update event
            yield _serialize_event(
                StreamEvent(
                    event_type="confidence_update",
                    node_name=step["node"],
                    data=step["confidence"],
                    timestamp=elapsed,
                )
            )

        elif step_type == "evidence":
            # Emit evidence found event
            yield _serialize_event(
                StreamEvent(
                    event_type="evidence_found",
                    node_name=step["node"],
                    data=step["evidence"],
                    timestamp=elapsed,
                )
            )

        else:
            # Emit node start event
            node_data: dict[str, Any] = {
                "questions_asked": step.get("question_number", 0),
                "question_number": step.get("question_number", 0),
                "stage": step.get("stage", ""),
                "stage_name": step.get("stage_name", ""),
            }
            # Include action/tool metadata for GatherInfo nodes
            for key in (
                "action_type",
                "action_detail",
                "tool_name",
                "data_source",
                "expected_info_gain",
                "current_category",
            ):
                if key in step:
                    node_data[key] = step[key]

            yield _serialize_event(
                StreamEvent(
                    event_type="node_start",
                    node_name=step["node"],
                    data=node_data,
                    timestamp=elapsed,
                )
            )

    # Final result event
    await asyncio.sleep(0.3)
    elapsed += 0.3
    result_data = scenario["result"].copy()
    result_data["total_duration"] = round(elapsed, 2)

    yield _serialize_event(
        StreamEvent(
            event_type="result",
            node_name="End",
            data=result_data,
            timestamp=elapsed,
        )
    )
