"""
Unit tests for agent type normalization inside run_planner.
Extracted and tested in isolation.
"""
import pytest

# The normalization map lives inside run_planner; replicate it here
_AGENT_TYPE_MAP = {
    "researchagent": "ResearchAgent",
    "researcher": "ResearchAgent",
    "research": "ResearchAgent",
    "writeragent": "WriterAgent",
    "writer": "WriterAgent",
    "writing": "WriterAgent",
    "analystagent": "AnalystAgent",
    "analyst": "AnalystAgent",
    "analysis": "AnalystAgent",
    "evaluatoragent": "EvaluatorAgent",
    "evaluator": "EvaluatorAgent",
    "planneragent": "PlannerAgent",
    "planner": "PlannerAgent",
}

def normalize(raw: str) -> str:
    return _AGENT_TYPE_MAP.get(raw.lower().strip(), raw)


@pytest.mark.parametrize("raw,expected", [
    ("ResearchAgent",  "ResearchAgent"),
    ("researcher",     "ResearchAgent"),
    ("RESEARCH",       "ResearchAgent"),
    ("  writer  ",     "WriterAgent"),
    ("WriterAgent",    "WriterAgent"),
    ("analyst",        "AnalystAgent"),
    ("AnalystAgent",   "AnalystAgent"),
    ("evaluator",      "EvaluatorAgent"),
    ("planner",        "PlannerAgent"),
    ("PlannerAgent",   "PlannerAgent"),
    # Unknown passes through as-is
    ("CustomAgent",    "CustomAgent"),
    ("my_special",     "my_special"),
])
def test_normalize_agent_type(raw, expected):
    assert normalize(raw) == expected
