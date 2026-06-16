"""
Unit tests for BaseAgent._parse_final_result.
Tests the JSON extraction logic in isolation — no DB, no Redis.
"""
import json
import types
import pytest

# Import the method logic directly without instantiating BaseAgent
# by extracting it into a standalone function for testing.
from aios.agents.base_agent import BaseAgent

def parse(content: str):
    """Call _parse_final_result without a real BaseAgent instance."""
    fake = types.SimpleNamespace()
    return BaseAgent._parse_final_result(fake, content)


class TestDirectJson:
    def test_plain_dict(self):
        assert parse('{"key": "value"}') == {"key": "value"}

    def test_nested_dict(self):
        result = parse('{"tasks": [{"title": "t1"}], "summary": "ok"}')
        assert result["summary"] == "ok"

    def test_with_whitespace(self):
        assert parse('  \n{"a": 1}\n  ') == {"a": 1}

    def test_array_is_rejected(self):
        assert parse('[1, 2, 3]') is None


class TestFencedCodeBlock:
    def test_json_fenced(self):
        content = '```json\n{"result": "done"}\n```'
        assert parse(content) == {"result": "done"}

    def test_plain_fenced(self):
        content = '```\n{"result": "done"}\n```'
        assert parse(content) == {"result": "done"}

    def test_fenced_with_surrounding_text(self):
        content = 'Here is the result:\n```json\n{"score": 9}\n```\nDone.'
        assert parse(content) == {"score": 9}


class TestBareJsonInText:
    def test_json_embedded_in_prose(self):
        content = 'I have finished. Here is my output: {"status": "ok", "count": 3} That is all.'
        result = parse(content)
        assert result == {"status": "ok", "count": 3}

    def test_picks_first_valid_object(self):
        # Should return the FIRST valid JSON object, not a greedy outer match
        content = 'Result: {"a": 1} and also {"b": 2}'
        result = parse(content)
        assert result == {"a": 1}

    def test_does_not_match_invalid_json(self):
        assert parse("no json here at all") is None

    def test_nested_json_in_tool_echo(self):
        # Regression: tool result JSON echoed back must not confuse the parser
        content = (
            'Tool returned: {"tool_result": "data"}\n'
            'My final answer: {"conclusion": "done", "confidence": 0.9}'
        )
        result = parse(content)
        # Should find the first valid JSON object
        assert isinstance(result, dict)
        assert "tool_result" in result or "conclusion" in result
