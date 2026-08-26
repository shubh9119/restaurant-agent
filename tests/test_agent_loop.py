"""Tests for the agent loop — end-to-end with StubLLM, no real LLM needed."""

import json
import pytest

from agent.agent_loop import AgentLoop
from agent.llm_client import LLMResponse, ToolCall
from agent.tools.registry import ToolRegistry
from tests.conftest import StubLLMClient


class TestAgentLoopBasic:
    """Basic agent loop tests."""

    def test_simple_text_response(self, mock_api, stub_llm):
        """Agent returns the LLM's text response directly."""
        llm = stub_llm([LLMResponse(content="Hello! Welcome to the restaurant.")])
        agent = AgentLoop(llm_client=llm)
        result = agent.process_message("Hi there")
        assert "Hello" in result or "Welcome" in result

    def test_history_accumulates(self, mock_api, stub_llm):
        """Conversation history should grow with each turn."""
        llm = stub_llm([
            LLMResponse(content="First response"),
            LLMResponse(content="Second response"),
        ])
        agent = AgentLoop(llm_client=llm)
        agent.process_message("Message 1")
        agent.process_message("Message 2")
        history = agent.get_history()
        assert len(history) == 4  # 2 user + 2 assistant

    def test_clear_history(self, mock_api, stub_llm):
        """clear_history should empty the conversation."""
        llm = stub_llm([LLMResponse(content="Hi")])
        agent = AgentLoop(llm_client=llm)
        agent.process_message("Hello")
        assert len(agent.get_history()) > 0
        agent.clear_history()
        assert len(agent.get_history()) == 0


class TestAgentLoopWithTools:
    """Agent loop tests involving tool calls."""

    def test_single_tool_call(self, mock_api, stub_llm):
        """Agent should call a tool and use the result."""
        llm = stub_llm([
            # First: LLM wants to call get_menu
            LLMResponse(tool_calls=[
                ToolCall(id="call_1", name="get_menu", arguments={}),
            ]),
            # Second: LLM produces text based on tool result
            LLMResponse(content="Here's our menu with 5 items!"),
        ])
        agent = AgentLoop(llm_client=llm)
        result = agent.process_message("Show me the menu")
        assert "5 items" in result or "menu" in result.lower()
        assert llm.calls_made == 2

    def test_multi_tool_call_sequence(self, mock_api, stub_llm):
        """Agent should handle check_availability → create_reservation → text."""
        llm = stub_llm([
            # Step 1: Check availability
            LLMResponse(tool_calls=[
                ToolCall(id="call_1", name="check_availability",
                         arguments={"date": "2026-08-27", "party_size": 3}),
            ]),
            # Step 2: Create reservation
            LLMResponse(tool_calls=[
                ToolCall(id="call_2", name="create_reservation",
                         arguments={
                             "customer_id": 1, "table_id": 5,
                             "date": "2026-08-27", "time": "19:00", "party_size": 3,
                         }),
            ]),
            # Step 3: Text response
            LLMResponse(content="Booked! Table 5 at 7 PM. Reservation ID 1."),
        ])
        agent = AgentLoop(llm_client=llm)
        result = agent.process_message("Book a table for 3 tomorrow at 7 PM")
        assert "Booked" in result or "Table" in result
        assert llm.calls_made == 3

    def test_booking_and_order_flow(self, mock_api, stub_llm):
        """Full flow: availability → book → add order items → text."""
        llm = stub_llm([
            LLMResponse(tool_calls=[
                ToolCall(id="c1", name="check_availability",
                         arguments={"date": "2026-08-27", "party_size": 2}),
            ]),
            LLMResponse(tool_calls=[
                ToolCall(id="c2", name="create_reservation",
                         arguments={"customer_id": 1, "table_id": 5,
                                    "date": "2026-08-27", "time": "20:00", "party_size": 2}),
            ]),
            LLMResponse(tool_calls=[
                ToolCall(id="c3", name="add_order_item",
                         arguments={"reservation_id": 1, "menu_item_id": 1, "quantity": 1}),
            ]),
            LLMResponse(content="All set! Table 5 at 8 PM with Paneer Tikka."),
        ])
        agent = AgentLoop(llm_client=llm)
        result = agent.process_message("Book for 2 at 8 PM and add paneer tikka")
        assert llm.calls_made == 4

    def test_max_iterations_guard(self, mock_api, stub_llm):
        """Agent should stop after max_iterations even if LLM keeps calling tools."""
        # Create an LLM that always returns tool calls
        infinite_tools = [
            LLMResponse(tool_calls=[
                ToolCall(id=f"call_{i}", name="get_menu", arguments={})
            ])
            for i in range(20)
        ]
        llm = stub_llm(infinite_tools)
        agent = AgentLoop(llm_client=llm, max_iterations=3)
        result = agent.process_message("Do something")
        # Should have stopped at 3 iterations
        assert llm.calls_made == 3
        assert "rephrasing" in result.lower() or "while" in result.lower()


class TestAgentLoopWithMemory:
    """Tests for customer context / memory in the agent loop."""

    def test_customer_context_in_system_prompt(self, mock_api, stub_llm):
        """Customer context should be injected into the system prompt."""
        context = {
            "id": 1,
            "name": "Priya Sharma",
            "preferences": {"seating_preference": "outdoor"},
            "recent_orders": "Paneer Tikka x1, Dal Makhani x2",
        }
        llm = stub_llm([LLMResponse(content="Welcome back, Priya!")])
        agent = AgentLoop(llm_client=llm, customer_context=context)
        agent.process_message("Hi")

        # Check system prompt includes customer context
        messages = llm.call_log[0]["messages"]
        system_msg = messages[0]["content"]
        assert "Priya Sharma" in system_msg
        assert "outdoor" in system_msg
        assert "Paneer Tikka" in system_msg
