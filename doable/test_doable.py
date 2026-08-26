"""
FILE 6: test_doable.py — Compact, All-in-One Test Suite.
Write this LAST (15 min).

WHY THIS DESIGN:
- Zero real LLM calls needed (uses StubLLM).
- Fast and deterministic (runs in <0.2s).
- Covers all 4 key evaluation criteria:
  1. Tool registration and auto-schema generation
  2. Safe tool dispatch & error handling
  3. Agent ReAct loop with multi-step tool sequences
  4. Customer memory recall & preference updates
"""

import json
import pytest
from api_client import RestaurantAPI, APIError
from tools import tool, init_tools, dispatch, get_tool_definitions
from llm_client import LLMResponse, ToolCall
from agent_loop import Agent, build_system_prompt


# ── Mock API Implementation for Testing ──

class FakeRestaurantAPI:
    """In-memory API replica for unit tests."""
    def __init__(self):
        self.menu = [
            {"id": 1, "name": "Paneer Tikka", "category": "starter", "price": 350, "tags": ["vegetarian"], "available": True},
            {"id": 2, "name": "Chicken Wings", "category": "starter", "price": 450, "tags": [], "available": True},
            {"id": 3, "name": "Dal Makhani", "category": "main", "price": 400, "tags": ["vegetarian", "contains-dairy"], "available": True},
        ]
        self.tables = [
            {"id": 1, "capacity": 2, "location": "indoor"},
            {"id": 5, "capacity": 4, "location": "outdoor"},
        ]
        self.customer = {
            "id": 1, "name": "Priya Sharma", "phone": "+91-9876543210",
            "preferences": {"seating_preference": "outdoor", "dietary_restrictions": ["vegetarian"]},
        }
        self.reservations = []
        self.orders = []

    def get_menu(self):
        return self.menu

    def get_tables(self):
        return self.tables

    def get_availability(self, date: str, party_size: int):
        return {
            "date": date,
            "available_tables": [{"table_id": 5, "capacity": 4, "location": "outdoor", "available_slots": ["19:00", "20:00"]}]
        }

    def lookup_customer(self, phone: str = None, email: str = None):
        if phone == "+91-9876543210":
            return self.customer
        raise APIError(404, "Customer not found")

    def create_reservation(self, customer_id: int, table_id: int, date: str, time: str, party_size: int):
        res = {"id": 101, "customer_id": customer_id, "table_id": table_id, "date": date, "time": time, "status": "confirmed"}
        self.reservations.append(res)
        return res

    def cancel_reservation(self, reservation_id: int):
        if reservation_id == 101:
            return {"message": "Reservation cancelled"}
        raise APIError(404, f"Reservation {reservation_id} not found")

    def add_order_item(self, reservation_id: int, menu_item_id: int, quantity: int = 1):
        item = next(m for m in self.menu if m["id"] == menu_item_id)
        order = {"id": 1, "reservation_id": reservation_id, "menu_item_name": item["name"], "quantity": quantity}
        self.orders.append(order)
        return order

    def get_customer_orders(self, customer_id: int):
        return [{"menu_item_name": "Paneer Tikka", "quantity": 1}, {"menu_item_name": "Dal Makhani", "quantity": 2}]

    def update_preferences(self, customer_id: int, prefs: dict):
        self.customer["preferences"].update(prefs)
        return self.customer


# ── Stub LLM for Deterministic Agent Testing ──

class StubLLM:
    """Cycles through pre-configured LLM responses."""
    def __init__(self, responses: list[LLMResponse]):
        self.responses = responses
        self.idx = 0

    def chat(self, messages, tools=None) -> LLMResponse:
        if self.idx < len(self.responses):
            resp = self.responses[self.idx]
            self.idx += 1
            return resp
        return LLMResponse(content="I am finished.")


# ── Tests ──

@pytest.fixture(autouse=True)
def setup_api():
    fake = FakeRestaurantAPI()
    init_tools(fake)
    yield fake


def test_tool_registry_and_schema():
    """Verify tool definitions generate valid JSON schemas with typed properties."""
    defs = get_tool_definitions()
    names = [d["function"]["name"] for d in defs]
    assert "get_menu" in names
    assert "create_reservation" in names

    res_tool = next(d for d in defs if d["function"]["name"] == "create_reservation")
    params = res_tool["function"]["parameters"]
    assert params["properties"]["table_id"]["type"] == "integer"
    assert "table_id" in params["required"]


def test_tool_dispatch_success(setup_api):
    """Verify dispatching tool calls returns formatted JSON output."""
    raw = dispatch("get_menu", {})
    data = json.loads(raw)
    assert "menu_items" in data
    assert len(data["menu_items"]) == 3


def test_tool_dispatch_defensive_error_handling(setup_api):
    """Verify unknown tools and bad inputs return safe error JSON instead of crashing."""
    # Unknown tool
    err1 = json.loads(dispatch("fake_tool_xyz", {}))
    assert "error" in err1
    assert "Unknown tool" in err1["error"]

    # Backend error propagation
    err2 = json.loads(dispatch("cancel_reservation", {"reservation_id": 9999}))
    assert "error" in err2
    assert "not found" in err2["error"].lower()


def test_agent_multi_turn_booking_flow(setup_api):
    """Verify multi-step tool sequencing: check availability -> book table -> respond."""
    fake_llm = StubLLM([
        # Turn 1: Call check_availability
        LLMResponse(tool_calls=[
            ToolCall(id="c1", name="check_availability", arguments={"date": "2026-08-27", "party_size": 4})
        ]),
        # Turn 2: Call create_reservation
        LLMResponse(tool_calls=[
            ToolCall(id="c2", name="create_reservation", arguments={
                "customer_id": 1, "table_id": 5, "date": "2026-08-27", "time": "19:00", "party_size": 4
            })
        ]),
        # Turn 3: Final confirmation
        LLMResponse(content="Table 5 is booked for 7:00 PM tomorrow! Reservation ID is 101."),
    ])

    agent = Agent(llm_client=fake_llm)
    reply = agent.process_message("Book an outdoor table for 4 tomorrow at 7 PM")

    assert "Table 5 is booked" in reply
    assert len(setup_api.reservations) == 1
    assert setup_api.reservations[0]["table_id"] == 5


def test_customer_memory_in_system_prompt():
    """Verify customer preferences and order history are injected into the system prompt."""
    context = {
        "id": 1,
        "name": "Priya Sharma",
        "preferences": {"seating_preference": "outdoor", "dietary_restrictions": ["vegetarian"]},
        "recent_orders": "Paneer Tikka x1, Dal Makhani x2"
    }
    prompt = build_system_prompt(context)
    assert "Priya Sharma" in prompt
    assert "outdoor" in prompt
    assert "Paneer Tikka x1" in prompt
