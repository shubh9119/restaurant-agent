"""Tests — 4 focused tests with StubLLM, no real LLM needed."""
import json
import pytest
from api_client import APIError
from tools import tool, init_tools, dispatch, get_tool_definitions
from llm_client import LLMResponse, ToolCall
from agent_loop import Agent, build_system_prompt


class FakeAPI:
    """In-memory API for testing."""
    def get_menu(self):
        return [
            {"id": 1, "name": "Paneer Tikka", "category": "starter", "price": 350, "tags": ["vegetarian"], "available": True},
            {"id": 2, "name": "Chicken Wings", "category": "starter", "price": 450, "tags": [], "available": True},
        ]
    def get_availability(self, date, party_size):
        return {"date": date, "available_tables": [{"table_id": 5, "capacity": 4, "location": "outdoor", "available_slots": ["19:00", "20:00"]}]}
    def create_reservation(self, customer_id, table_id, date, time, party_size):
        return {"id": 101, "customer_id": customer_id, "table_id": table_id, "date": date, "time": time, "status": "confirmed"}
    def cancel_reservation(self, rid):
        if rid == 101: return {"message": "Cancelled"}
        raise APIError(404, "Not found")
    def add_order_item(self, rid, mid, quantity=1):
        return {"id": 1, "reservation_id": rid, "menu_item_name": "Paneer Tikka", "quantity": quantity}
    def get_customer_orders(self, cid):
        return [{"menu_item_name": "Paneer Tikka", "quantity": 1}]
    def lookup_customer(self, phone=None, email=None):
        if phone == "+91-9876543210":
            return {"id": 1, "name": "Priya", "preferences": {"seating_preference": "outdoor"}}
        raise APIError(404, "Not found")


class StubLLM:
    """Returns pre-programmed responses."""
    def __init__(self, responses):
        self.responses = responses
        self.idx = 0
    def chat(self, messages, tools=None):
        if self.idx < len(self.responses):
            r = self.responses[self.idx]; self.idx += 1; return r
        return LLMResponse(content="Done.")


@pytest.fixture(autouse=True)
def setup():
    init_tools(FakeAPI())


def test_tool_schema_generation():
    defs = get_tool_definitions()
    names = [d["function"]["name"] for d in defs]
    assert "get_menu" in names
    assert "create_reservation" in names
    res = next(d for d in defs if d["function"]["name"] == "create_reservation")
    assert res["function"]["parameters"]["properties"]["table_id"]["type"] == "integer"


def test_dispatch_and_error_handling():
    # Success
    data = json.loads(dispatch("get_menu", {}))
    assert "menu_items" in data
    # Unknown tool
    err = json.loads(dispatch("fake_tool", {}))
    assert "error" in err
    # Backend error
    err2 = json.loads(dispatch("cancel_reservation", {"reservation_id": 9999}))
    assert "error" in err2


def test_agent_booking_flow():
    llm = StubLLM([
        LLMResponse(tool_calls=[ToolCall("c1", "check_availability", {"date": "2026-08-27", "party_size": 4})]),
        LLMResponse(tool_calls=[ToolCall("c2", "create_reservation", {"customer_id": 1, "table_id": 5, "date": "2026-08-27", "time": "19:00", "party_size": 4})]),
        LLMResponse(content="Booked Table 5 at 7 PM! Reservation ID 101."),
    ])
    agent = Agent(llm_client=llm)
    reply = agent.process_message("Book a table for 4 at 7 PM")
    assert "101" in reply


def test_customer_memory():
    context = {"name": "Priya", "id": 1, "preferences": {"seating_preference": "outdoor"}, "recent_orders": "Paneer Tikka x1"}
    prompt = build_system_prompt(context)
    assert "Priya" in prompt and "outdoor" in prompt and "Paneer Tikka" in prompt
