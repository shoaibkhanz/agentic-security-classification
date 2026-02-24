"""
Simulated securities data for tutorial exercises.

This module provides ~20 fake private securities with varying levels
of information availability. Some have full documentation, others
have minimal info — this simulates the real challenge of classifying
private securities.

Production note: In a real system, this would be a database.
For learning purposes, we use in-memory data with realistic structure.
"""

from __future__ import annotations

from datetime import date

from shared.models import (
    ExemptionType,
    SECAdvisory,
    SearchResult,
    SecurityInfo,
)

# =============================================================================
# Securities Database
# =============================================================================

SECURITIES_DATABASE: list[SecurityInfo] = [
    # --- Easy: Clear classification with full documentation ---
    SecurityInfo(
        name="Meridian Growth Fund LP",
        issuer="Meridian Capital Partners",
        type_hint="limited partnership interest",
        offering_amount=75_000_000,
        min_investment=250_000,
        offering_date=date(2024, 3, 15),
        exemption=ExemptionType.REG_D_506C,
        limited_info=False,
        raw_description=(
            "Meridian Growth Fund LP offers limited partnership interests "
            "in a diversified private equity fund. The fund targets mid-market "
            "buyouts in technology and healthcare sectors. Minimum investment "
            "of $250,000. Accredited investors only."
        ),
    ),
    SecurityInfo(
        name="Atlas Senior Secured Notes 2024",
        issuer="Atlas Infrastructure Corp",
        type_hint="senior secured notes",
        offering_amount=25_000_000,
        min_investment=50_000,
        offering_date=date(2024, 6, 1),
        maturity_date=date(2027, 6, 1),
        interest_rate=0.085,
        exemption=ExemptionType.REG_D_506B,
        limited_info=False,
        raw_description=(
            "Atlas Infrastructure Corp is offering $25M in 3-year senior "
            "secured notes bearing 8.5% annual interest, paid quarterly. "
            "Notes are secured by the company's infrastructure asset portfolio. "
            "Available to accredited investors under Reg D 506(b)."
        ),
    ),
    SecurityInfo(
        name="NovaTech SAFE Round",
        issuer="NovaTech AI Inc",
        type_hint="SAFE",
        offering_amount=5_000_000,
        min_investment=25_000,
        offering_date=date(2024, 9, 10),
        conversion_terms="Converts at next priced round with 20% discount, $20M valuation cap",
        exemption=ExemptionType.REG_D_506B,
        limited_info=False,
        raw_description=(
            "NovaTech AI Inc is raising $5M via Simple Agreement for Future "
            "Equity (SAFE) instruments. 20% discount to next priced round, "
            "$20M valuation cap. Y Combinator standard SAFE terms."
        ),
    ),
    SecurityInfo(
        name="Pacific Heights Residences Fund",
        issuer="Pacific Heights Real Estate LLC",
        type_hint="real estate fund interest",
        offering_amount=40_000_000,
        min_investment=100_000,
        offering_date=date(2024, 1, 20),
        exemption=ExemptionType.REG_D_506C,
        limited_info=False,
        raw_description=(
            "Pacific Heights Residences Fund offers membership interests in "
            "a real estate investment vehicle targeting luxury multifamily "
            "properties in the San Francisco Bay Area. Target IRR of 15-18%. "
            "5-year hold period."
        ),
    ),
    # --- Medium: Some ambiguity, partial information ---
    SecurityInfo(
        name="Catalyst Convertible Note Series A",
        issuer="Catalyst Biotech Inc",
        type_hint="convertible note",
        offering_amount=3_000_000,
        min_investment=10_000,
        offering_date=date(2024, 7, 1),
        maturity_date=date(2026, 7, 1),
        interest_rate=0.06,
        conversion_terms="Converts at Series A with 25% discount or $15M cap",
        exemption=ExemptionType.REG_D_506B,
        limited_info=False,
        raw_description=(
            "Convertible promissory note. 6% annual interest. Auto-converts "
            "at qualified financing of $5M+. 25% discount or $15M valuation "
            "cap, whichever is more favorable to the holder."
        ),
    ),
    SecurityInfo(
        name="Riverview Revenue Participation",
        issuer="Riverview SaaS Corp",
        type_hint=None,
        offering_amount=2_000_000,
        min_investment=5_000,
        offering_date=date(2024, 4, 15),
        exemption=ExemptionType.REG_CF,
        limited_info=True,
        raw_description=(
            "Participate in Riverview's growth. Investors receive a share "
            "of monthly recurring revenue until 2x their investment is returned, "
            "then 0.5% of revenue in perpetuity. Not equity, not debt."
        ),
    ),
    SecurityInfo(
        name="Quantum Series B Preferred",
        issuer="Quantum Computing Labs",
        type_hint="preferred stock",
        offering_amount=50_000_000,
        min_investment=500_000,
        offering_date=date(2024, 11, 1),
        exemption=ExemptionType.REG_D_506C,
        limited_info=False,
        raw_description=(
            "Series B Preferred Stock offering. 1x non-participating liquidation "
            "preference. Anti-dilution protection. Board observer seat for "
            "investors of $2M+. Pre-money valuation: $200M."
        ),
    ),
    SecurityInfo(
        name="Harbor Bridge Notes 2025",
        issuer="Harbor Bridge Capital",
        type_hint="promissory notes",
        offering_amount=10_000_000,
        min_investment=25_000,
        offering_date=date(2024, 8, 1),
        maturity_date=date(2025, 8, 1),
        interest_rate=0.12,
        exemption=ExemptionType.REG_D_506B,
        limited_info=True,
        raw_description=(
            "Short-term promissory notes. 12% annual interest paid monthly. "
            "12-month maturity. Secured by portfolio of merchant cash advance "
            "receivables."
        ),
    ),
    # --- Hard: Minimal info, exotic structures ---
    SecurityInfo(
        name="Zenith Opportunity Vehicle",
        issuer="Zenith Partners",
        type_hint=None,
        offering_amount=None,
        min_investment=None,
        offering_date=date(2024, 5, 1),
        exemption=ExemptionType.UNKNOWN,
        limited_info=True,
        raw_description=(
            "Special purpose vehicle for qualified purchasers. "
            "Details available upon request."
        ),
    ),
    SecurityInfo(
        name="Greenfield Token Offering",
        issuer="Greenfield Protocol Foundation",
        type_hint=None,
        offering_amount=15_000_000,
        min_investment=1_000,
        offering_date=date(2024, 10, 1),
        exemption=ExemptionType.REG_D_506C,
        limited_info=True,
        raw_description=(
            "Token-based investment instrument. Tokens represent a claim on "
            "future protocol revenues. Not a security per issuer's legal opinion, "
            "but structured with investment contract characteristics."
        ),
    ),
    SecurityInfo(
        name="Phoenix Restructured Equity",
        issuer="Phoenix Holdings LLC",
        type_hint="restructured equity",
        offering_amount=8_000_000,
        min_investment=50_000,
        offering_date=date(2024, 2, 1),
        exemption=ExemptionType.SECTION_4A2,
        limited_info=True,
        raw_description=(
            "Post-restructuring equity in Phoenix Holdings. Former debt "
            "holders received equity in exchange for debt forgiveness. "
            "Complex capital structure with multiple tranches."
        ),
    ),
    SecurityInfo(
        name="Orion Agricultural Income Fund",
        issuer="Orion Farmland Partners",
        type_hint="agricultural fund",
        offering_amount=20_000_000,
        min_investment=100_000,
        offering_date=date(2024, 3, 1),
        exemption=ExemptionType.REG_D_506B,
        limited_info=False,
        raw_description=(
            "Income-generating agricultural fund. Investors receive quarterly "
            "distributions from crop revenues and land appreciation. "
            "10-year fund life. Farmland assets in Iowa and Nebraska."
        ),
    ),
    # --- Edge cases: Could be classified multiple ways ---
    SecurityInfo(
        name="Apex Hybrid Instrument 2024",
        issuer="Apex Financial Group",
        type_hint="hybrid",
        offering_amount=12_000_000,
        min_investment=75_000,
        offering_date=date(2024, 6, 15),
        maturity_date=date(2029, 6, 15),
        interest_rate=0.04,
        conversion_terms="Mandatory conversion at maturity into common equity at $10/share",
        exemption=ExemptionType.REG_D_506C,
        limited_info=False,
        raw_description=(
            "Hybrid instrument paying 4% coupon with mandatory conversion to "
            "common equity at maturity. Functions as debt during term, becomes "
            "equity at maturity. 5-year duration."
        ),
    ),
    SecurityInfo(
        name="Cascade SAFE+Note",
        issuer="Cascade Robotics",
        type_hint="SAFE with note features",
        offering_amount=2_500_000,
        min_investment=10_000,
        offering_date=date(2024, 8, 20),
        maturity_date=date(2026, 8, 20),
        interest_rate=0.05,
        conversion_terms="Converts like SAFE at next round, but accrues 5% interest until conversion",
        exemption=ExemptionType.REG_D_506B,
        limited_info=True,
        raw_description=(
            "Hybrid SAFE with note-like features. Accrues 5% interest, "
            "converts at next priced round with 20% discount, $10M cap. "
            "If no priced round by maturity, converts to common at cap."
        ),
    ),
    # --- Adversarial: Misleading information ---
    SecurityInfo(
        name="Diamond Legacy Trust Units",
        issuer="Diamond Legacy Trust",
        type_hint="trust units",
        offering_amount=100_000_000,
        min_investment=500_000,
        offering_date=date(2024, 1, 1),
        exemption=ExemptionType.UNKNOWN,
        limited_info=True,
        raw_description=(
            "Guaranteed 25% annual returns. Trust units backed by proprietary "
            "AI-driven cryptocurrency arbitrage strategy. Limited availability. "
            "Principal guaranteed by issuer."
        ),
    ),
    SecurityInfo(
        name="Stellar Community Solar Bonds",
        issuer="Stellar Energy Cooperative",
        type_hint="bonds",
        offering_amount=5_000_000,
        min_investment=1_000,
        offering_date=date(2024, 9, 1),
        maturity_date=date(2034, 9, 1),
        interest_rate=0.045,
        exemption=ExemptionType.REG_A_PLUS,
        limited_info=False,
        raw_description=(
            "Community solar bonds funding installation of solar panels on "
            "public buildings. 4.5% annual coupon. 10-year maturity. "
            "Issued by an energy cooperative under Reg A+. "
            "Non-accredited investors welcome."
        ),
    ),
    SecurityInfo(
        name="Aegis Preferred Equity Fund III",
        issuer="Aegis Capital Management",
        type_hint="preferred equity fund",
        offering_amount=60_000_000,
        min_investment=250_000,
        offering_date=date(2024, 4, 1),
        exemption=ExemptionType.REG_D_506C,
        limited_info=False,
        raw_description=(
            "Aegis Preferred Equity Fund III invests in preferred equity "
            "positions in commercial real estate properties. Target net IRR "
            "of 12-15%. 7-year fund life with 2 one-year extensions. "
            "Quarterly distributions."
        ),
    ),
    SecurityInfo(
        name="Vortex Special Situations Note",
        issuer="Vortex Capital",
        type_hint=None,
        offering_amount=None,
        min_investment=100_000,
        offering_date=date(2024, 7, 15),
        exemption=ExemptionType.SECTION_4A2,
        limited_info=True,
        raw_description=(
            "Bespoke investment instrument for sophisticated investors. "
            "Returns linked to performance of distressed debt portfolio. "
            "Contact for details."
        ),
    ),
]

# =============================================================================
# SEC Filings Database
# =============================================================================

SEC_FILINGS: list[SECAdvisory] = [
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 3, 20),
        issuer="Meridian Capital Partners",
        exemption_type=ExemptionType.REG_D_506C,
        amount_raised=75_000_000,
        details="Limited partnership interests in private equity fund. 506(c) with general solicitation.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 6, 5),
        issuer="Atlas Infrastructure Corp",
        exemption_type=ExemptionType.REG_D_506B,
        amount_raised=25_000_000,
        details="Senior secured notes. 3-year term. Infrastructure assets.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 9, 15),
        issuer="NovaTech AI Inc",
        exemption_type=ExemptionType.REG_D_506B,
        amount_raised=5_000_000,
        details="SAFE instruments. Pre-seed round. AI/ML startup.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 1, 25),
        issuer="Pacific Heights Real Estate LLC",
        exemption_type=ExemptionType.REG_D_506C,
        amount_raised=40_000_000,
        details="Real estate fund. Multifamily properties. Bay Area.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 7, 5),
        issuer="Catalyst Biotech Inc",
        exemption_type=ExemptionType.REG_D_506B,
        amount_raised=3_000_000,
        details="Convertible notes. Biotech early stage.",
    ),
    SECAdvisory(
        filing_type="Form C",
        filing_date=date(2024, 4, 20),
        issuer="Riverview SaaS Corp",
        exemption_type=ExemptionType.REG_CF,
        amount_raised=2_000_000,
        details="Revenue participation agreement. Regulation Crowdfunding.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 11, 5),
        issuer="Quantum Computing Labs",
        exemption_type=ExemptionType.REG_D_506C,
        amount_raised=50_000_000,
        details="Series B Preferred Stock. Quantum computing.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 10, 5),
        issuer="Greenfield Protocol Foundation",
        exemption_type=ExemptionType.REG_D_506C,
        amount_raised=15_000_000,
        details="Token offering. Blockchain protocol. Classification disputed.",
    ),
    SECAdvisory(
        filing_type="Form 1-A",
        filing_date=date(2024, 9, 5),
        issuer="Stellar Energy Cooperative",
        exemption_type=ExemptionType.REG_A_PLUS,
        amount_raised=5_000_000,
        details="Community solar bonds. Regulation A+ Tier 2. Energy cooperative.",
    ),
    SECAdvisory(
        filing_type="Form D",
        filing_date=date(2024, 4, 5),
        issuer="Aegis Capital Management",
        exemption_type=ExemptionType.REG_D_506C,
        amount_raised=60_000_000,
        details="Preferred equity fund. Commercial real estate.",
    ),
]

# =============================================================================
# Simulated Web Search Results
# =============================================================================

WEB_SEARCH_RESULTS: dict[str, list[SearchResult]] = {
    "meridian capital partners fund": [
        SearchResult(
            title="Meridian Capital Partners - Firm Overview",
            snippet="Meridian Capital Partners manages $2B+ in private equity. Founded 2010.",
            url="https://example.com/meridian",
            relevance_score=0.95,
        ),
    ],
    "novatech ai inc funding": [
        SearchResult(
            title="NovaTech AI Raises $5M in SAFE Round",
            snippet="NovaTech AI, an enterprise AI startup, raised $5M via SAFE instruments.",
            url="https://example.com/novatech",
            relevance_score=0.90,
        ),
    ],
    "diamond legacy trust": [
        SearchResult(
            title="SEC Warning: Diamond Legacy Trust Under Investigation",
            snippet="SEC has issued a warning about Diamond Legacy Trust. Guaranteed returns claim under scrutiny.",
            url="https://example.com/sec-warning",
            relevance_score=0.98,
        ),
        SearchResult(
            title="Investor Alert: Too-Good-to-Be-True Returns",
            snippet="Investment schemes promising guaranteed 25%+ returns are red flags per SEC guidance.",
            url="https://example.com/investor-alert",
            relevance_score=0.85,
        ),
    ],
    "greenfield protocol foundation token": [
        SearchResult(
            title="Greenfield Protocol: Token or Security?",
            snippet="Legal experts debate whether Greenfield tokens constitute securities under the Howey test.",
            url="https://example.com/greenfield-debate",
            relevance_score=0.88,
        ),
    ],
    "vortex capital special situations": [
        SearchResult(
            title="Vortex Capital - Distressed Debt Specialists",
            snippet="Vortex Capital focuses on distressed debt and special situations. $500M AUM.",
            url="https://example.com/vortex",
            relevance_score=0.82,
        ),
    ],
}
