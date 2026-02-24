"""
Capstone: Private Securities Classification Agent
===================================================

An intelligent agent system that classifies private securities by asking
the RIGHT questions adaptively, using tools to research via web search,
database lookups, and SEC filings.

Core design: The agent optimizes for CONFIDENCE -- it tracks a running
confidence estimate and picks the next action that would most increase
confidence toward a threshold. It stops gathering info when confidence
is high enough.

Architecture:
  Graph (structure) + Agents (intelligence)

  InitialAssessment -> GatherInfo -> AssessConfidence
    -> [low confidence] PlanNextAction -> GatherInfo (loop)
    -> [high confidence] Classify -> Verify -> End

Run:
  uv run python -m capstone.run
"""
