"""Tests for error handling — backend errors, malformed tool calls, edge cases."""

import json
import pytest

from agent.tools.registry import ToolRegistry
from agent.agent_loop import AgentLoop
from agent.llm_client import LLMResponse, ToolCall
from agent.api_client import APIError
from tests.conftest import StubLLMClient


class TestBackendErrorPropagation:
    """Backend HTTP errors should be caught by tools and returned as error JSON."""

    def test_lookup_nonexistent_customer_returns_error(self, mock_api):
        result = json.loads(ToolRegistry.dispatch("lookup_customer", {"phone": "+00-0000"}))
        assert "error" in result

    def test_get_nonexistent_reservation_returns_error(self, mock_api):
        result = json.loads(ToolRegistry.dispatch("get_reservation", {"reservation_id": 9999}))
        assert "error" in result

    def test_cancel_nonexistent_reservation_returns_error(self, mock_api):
        result = json.loads(ToolRegistry.dispatch("cancel_reservation", {"reservation_id": 9999}))
        assert "error" in result


class TestMalformedToolCalls:
    """Tests for when the LLM produces bad tool calls."""

    def test_unknown_tool_name(self, mock_api):
        """Dispatching a hallucinated tool name returns an error."""
        result = json.loads(ToolRegistry.dispatch("hallucinated_tool", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_empty_arguments(self, mock_api):
        """Dispatching with empty args to a tool that needs args returns error."""
        result = json.loads(ToolRegistry.dispatch("create_reservation", {}))
        assert "error" in result

    def test_none_arguments_treated_as_empty(self, mock_api):
        """None arguments should be treated as empty dict."""
        result = json.loads(ToolRegistry.dispatch("get_menu", None))
        # get_menu has no required args, should succeed
        assert "menu_items" in result

    def test_string_arguments_parsed(self, mock_api):
        """String arguments should be JSON-parsed."""
        result = json.loads(ToolRegistry.dispatch("get_menu", "{}"))
        assert "menu_items" in result

    def test_invalid_json_string_arguments(self, mock_api):
        """Invalid JSON string should return error."""
        result = json.loads(ToolRegistry.dispatch("get_menu", "{invalid json"))
        assert "error" in result


class TestAgentErrorRecovery:
    """Test that the agent loop handles errors gracefully."""

    def test_llm_exception_caught(self, mock_api):
        """If the LLM throws, agent should return an error message, not crash."""
        class FailingLLM:
            def chat(self, messages, tools=None):
                raise ConnectionError("API unreachable")

        agent = AgentLoop(llm_client=FailingLLM())
        result = agent.process_message("Hello")
        assert "technical issue" in result.lower() or "sorry" in result.lower()

    def test_tool_error_flows_back_to_llm(self, mock_api, stub_llm):
        """When a tool returns an error, the LLM should see it and respond."""
        llm = stub_llm([
            # LLM tries to cancel a nonexistent reservation
            LLMResponse(tool_calls=[
                ToolCall(id="c1", name="cancel_reservation",
                         arguments={"reservation_id": 9999}),
            ]),
            # LLM should get the error and respond to user
            LLMResponse(content="I couldn't find that reservation. Could you check the ID?"),
        ])
        agent = AgentLoop(llm_client=llm)
        result = agent.process_message("Cancel reservation 9999")

        # The LLM should have been called twice
        assert llm.calls_made == 2
        # The tool error should be in the history
        history = agent.get_history()
        tool_results = [m for m in history if m.get("role") == "tool"]
        assert len(tool_results) == 1
        assert "error" in tool_results[0]["content"].lower()

    def test_multiple_parallel_tool_calls(self, mock_api, stub_llm):
        """Agent handles multiple tool calls in a single LLM response."""
        llm = stub_llm([
            # LLM calls two tools at once
            LLMResponse(tool_calls=[
                ToolCall(id="c1", name="get_menu", arguments={}),
                ToolCall(id="c2", name="list_tables", arguments={}),
            ]),
            LLMResponse(content="We have 5 menu items and 3 tables."),
        ])
        agent = AgentLoop(llm_client=llm)
        result = agent.process_message("Tell me about the menu and tables")
        assert llm.calls_made == 2
        # Should have 2 tool results in history
        history = agent.get_history()
        tool_results = [m for m in history if m.get("role") == "tool"]
        assert len(tool_results) == 2
