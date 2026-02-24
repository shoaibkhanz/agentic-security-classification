"""
Reusable dependency patterns for the tutorial curriculum.

These simulate the external services an agent would use in production:
- Securities database (SQL-like queries)
- SEC filing search (EDGAR API)
- Web search (general internet search)

Production note: Dependencies are injected via pydantic-ai's RunContext.
This means agents are testable — swap real deps for fakes in tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.fake_data import SEC_FILINGS, SECURITIES_DATABASE, WEB_SEARCH_RESULTS
from shared.models import SECAdvisory, SearchResult, SecurityInfo


@dataclass
class SecuritiesDB:
    """
    Simulated securities database.

    In production, this would wrap an async database client (asyncpg, SQLAlchemy).
    For learning, we use in-memory data with realistic async interfaces.
    """

    async def search(self, query: str) -> list[SecurityInfo]:
        """Search securities by name, issuer, or description."""
        query_lower = query.lower()
        return [
            sec
            for sec in SECURITIES_DATABASE
            if query_lower in sec.name.lower()
            or query_lower in sec.issuer.lower()
            or query_lower in sec.raw_description.lower()
        ]

    async def get_by_name(self, name: str) -> SecurityInfo | None:
        """Get a specific security by exact name."""
        for sec in SECURITIES_DATABASE:
            if sec.name.lower() == name.lower():
                return sec
        return None

    async def get_by_issuer(self, issuer: str) -> list[SecurityInfo]:
        """Get all securities from a specific issuer."""
        issuer_lower = issuer.lower()
        return [
            sec for sec in SECURITIES_DATABASE if issuer_lower in sec.issuer.lower()
        ]

    async def query(self, sql: str) -> list[dict[str, object]]:
        """
        Execute a SQL-like query against the securities database.

        This simulates SQL querying. In production, you'd use a real DB client.
        For the tutorial, we parse basic SELECT patterns.
        """
        sql_lower = sql.lower()

        # Simple pattern matching for common queries
        if "where" in sql_lower:
            # Extract the condition value (very simplified)
            results = []
            for sec in SECURITIES_DATABASE:
                sec_dict = sec.model_dump()
                # Check if any field matches any word in the WHERE clause
                for field_value in sec_dict.values():
                    if isinstance(field_value, str) and any(
                        word in field_value.lower()
                        for word in sql_lower.split()
                        if len(word) > 3  # Skip short SQL keywords
                    ):
                        results.append(sec_dict)
                        break
            return results  # type: ignore[return-value]

        # Default: return all securities as dicts
        return [sec.model_dump() for sec in SECURITIES_DATABASE[:5]]  # type: ignore[return-value]

    async def list_all(self) -> list[SecurityInfo]:
        """List all securities in the database."""
        return list(SECURITIES_DATABASE)


@dataclass
class SECFilingSearch:
    """
    Simulated SEC EDGAR filing search.

    In production, this would call the SEC EDGAR API or a data provider.
    """

    async def search_by_issuer(self, issuer: str) -> list[SECAdvisory]:
        """Search SEC filings by issuer name."""
        issuer_lower = issuer.lower()
        return [
            filing for filing in SEC_FILINGS if issuer_lower in filing.issuer.lower()
        ]

    async def search_by_filing_type(
        self,
        filing_type: str,
        issuer: str | None = None,
    ) -> list[SECAdvisory]:
        """Search by filing type, optionally filtered by issuer."""
        results = [
            f for f in SEC_FILINGS if f.filing_type.lower() == filing_type.lower()
        ]
        if issuer:
            issuer_lower = issuer.lower()
            results = [f for f in results if issuer_lower in f.issuer.lower()]
        return results

    async def search(self, query: str) -> list[SECAdvisory]:
        """General search across all filing fields."""
        query_lower = query.lower()
        return [
            filing
            for filing in SEC_FILINGS
            if query_lower in filing.issuer.lower()
            or query_lower in filing.details.lower()
            or query_lower in filing.filing_type.lower()
        ]


@dataclass
class WebSearchClient:
    """
    Simulated web search client.

    In production, this would call a search API (Brave, Serper, Tavily).
    """

    async def search(self, query: str) -> list[SearchResult]:
        """Search the web for information about a security or issuer."""
        query_lower = query.lower()

        # Check for matching pre-built results
        for key, results in WEB_SEARCH_RESULTS.items():
            if any(word in query_lower for word in key.split() if len(word) > 3):
                return results

        # Default: no results found
        return [
            SearchResult(
                title=f"No specific results for: {query}",
                snippet="Limited public information available for this private security.",
                url="https://example.com/no-results",
                relevance_score=0.1,
            )
        ]


@dataclass
class AnalystContext:
    """
    Combined dependencies for a securities analyst agent.

    This is the typical production pattern: bundle all services
    into a single deps dataclass that gets injected via RunContext.
    """

    db: SecuritiesDB
    sec_search: SECFilingSearch
    web_search: WebSearchClient
    analyst_name: str = "Default Analyst"
    access_level: str = "standard"  # "standard" | "senior" | "admin"

    @classmethod
    def create(
        cls,
        analyst_name: str = "Tutorial User",
        access_level: str = "standard",
    ) -> AnalystContext:
        """Factory method to create a fully initialized context."""
        return cls(
            db=SecuritiesDB(),
            sec_search=SECFilingSearch(),
            web_search=WebSearchClient(),
            analyst_name=analyst_name,
            access_level=access_level,
        )
