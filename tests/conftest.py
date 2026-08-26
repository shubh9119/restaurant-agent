"""Shared test fixtures — stub LLM, mock API client, test data."""

import json
import pytest
from typing import Any, Optional
from unittest.mock import MagicMock

from agent.llm_client import BaseLLMClient, LLMResponse, ToolCall
from agent.api_client import RestaurantAPIClient, APIError
from agent.tools.registry import ToolRegistry


# ── Stub LLM ────────────────────────────────────────────────────────────────

class StubLLMClient(BaseLLMClient):
    """A fake LLM that returns pre-programmed responses in sequence.

    Usage:
        stub = StubLLMClient([
            LLMResponse(tool_calls=[ToolCall(id="1", name="get_menu", arguments={})]),
            LLMResponse(content="Here's our menu!"),
        ])
    """

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self._call_count = 0
        self.call_log: list[dict] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        self.call_log.append({"messages": messages, "tools": tools})
        if self._call_count >= len(self._responses):
            return LLMResponse(content="[StubLLM] No more responses.")
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    @property
    def calls_made(self) -> int:
        return self._call_count


# ── Mock API Client ─────────────────────────────────────────────────────────

class MockAPIClient:
    """A mock RestaurantAPIClient with canned responses for testing tools."""

    def __init__(self):
        self._menu = [
            {"id": 1, "name": "Paneer Tikka", "category": "starter", "price": 350.0,
             "tags": ["vegetarian"], "available": True},
            {"id": 2, "name": "Chicken Wings", "category": "starter", "price": 450.0,
             "tags": [], "available": True},
            {"id": 5, "name": "Dal Makhani", "category": "main", "price": 400.0,
             "tags": ["vegetarian", "contains-dairy"], "available": True},
            {"id": 9, "name": "Gulab Jamun", "category": "dessert", "price": 200.0,
             "tags": ["vegetarian", "contains-dairy"], "available": True},
            {"id": 10, "name": "Tiramisu", "category": "dessert", "price": 350.0,
             "tags": ["vegetarian", "contains-nuts", "contains-dairy"], "available": False},
        ]
        self._tables = [
            {"id": 1, "capacity": 2, "location": "indoor"},
            {"id": 5, "capacity": 4, "location": "outdoor"},
            {"id": 7, "capacity": 4, "location": "outdoor"},
        ]
        self._customers = {
            1: {"id": 1, "name": "Priya Sharma", "phone": "+91-9876543210",
                "email": "priya@example.com",
                "preferences": {"seating_preference": "outdoor", "dietary_restrictions": ["vegetarian"]}},
        }
        self._reservations = {}
        self._orders = {}
        self._next_res_id = 1
        self._next_order_id = 1

    def get_menu(self) -> list[dict]:
        return self._menu

    def get_tables(self) -> list[dict]:
        return self._tables

    def get_availability(self, date: str, party_size: int) -> dict:
        fitting = [t for t in self._tables if t["capacity"] >= party_size]
        return {
            "date": date, "party_size": party_size,
            "available_tables": [
                {"table_id": t["id"], "capacity": t["capacity"], "location": t["location"],
                 "available_slots": ["19:00", "19:30", "20:00"]}
                for t in fitting
            ],
        }

    def lookup_customer(self, phone: Optional[str] = None, email: Optional[str] = None) -> dict:
        for c in self._customers.values():
            if phone and c["phone"] == phone:
                return c
            if email and c.get("email") == email:
                return c
        raise APIError(404, "Customer not found.")

    def get_customer(self, customer_id: int) -> dict:
        if customer_id in self._customers:
            return self._customers[customer_id]
        raise APIError(404, f"Customer {customer_id} not found.")

    def create_customer(self, name: str, phone: str, email: Optional[str] = None) -> dict:
        cust = {"id": 99, "name": name, "phone": phone, "email": email, "preferences": {}}
        self._customers[99] = cust
        return cust

    def update_preferences(self, customer_id: int, preferences: dict) -> dict:
        if customer_id not in self._customers:
            raise APIError(404, f"Customer {customer_id} not found.")
        self._customers[customer_id]["preferences"].update(preferences)
        return self._customers[customer_id]

    def get_customer_reservations(self, customer_id: int) -> list[dict]:
        return [r for r in self._reservations.values() if r["customer_id"] == customer_id]

    def get_customer_orders(self, customer_id: int) -> list[dict]:
        return [
            {"menu_item_name": "Paneer Tikka", "quantity": 1},
            {"menu_item_name": "Dal Makhani", "quantity": 2},
        ]

    def create_reservation(self, customer_id: int, table_id: int, date: str, time: str, party_size: int) -> dict:
        res = {
            "id": self._next_res_id, "customer_id": customer_id, "table_id": table_id,
            "date": date, "time": time, "party_size": party_size, "status": "confirmed",
        }
        self._reservations[self._next_res_id] = res
        self._next_res_id += 1
        return res

    def get_reservation(self, reservation_id: int) -> dict:
        if reservation_id in self._reservations:
            return self._reservations[reservation_id]
        raise APIError(404, f"Reservation {reservation_id} not found.")

    def cancel_reservation(self, reservation_id: int) -> dict:
        if reservation_id not in self._reservations:
            raise APIError(404, f"Reservation {reservation_id} not found.")
        self._reservations[reservation_id]["status"] = "cancelled"
        return {"message": "Reservation cancelled.", "reservation": self._reservations[reservation_id]}

    def add_order_item(self, reservation_id: int, menu_item_id: int, quantity: int = 1) -> dict:
        order = {
            "id": self._next_order_id, "reservation_id": reservation_id,
            "menu_item_id": menu_item_id, "menu_item_name": f"Item {menu_item_id}",
            "quantity": quantity, "price": 100.0,
        }
        self._orders[self._next_order_id] = order
        self._next_order_id += 1
        return order

    def get_reservation_orders(self, reservation_id: int) -> list[dict]:
        return [o for o in self._orders.values() if o["reservation_id"] == reservation_id]

    def remove_order_item(self, reservation_id: int, order_id: int) -> dict:
        if order_id in self._orders:
            removed = self._orders.pop(order_id)
            return {"message": "Order item removed.", "order": removed}
        raise APIError(404, f"Order {order_id} not found.")

    def close(self):
        pass


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_api():
    """Provide a MockAPIClient and register it with the ToolRegistry."""
    client = MockAPIClient()
    ToolRegistry.set_api_client(client)
    yield client
    ToolRegistry._api_client = None


@pytest.fixture
def stub_llm():
    """Factory fixture to create StubLLMClients with given responses."""
    def _make(responses: list[LLMResponse]) -> StubLLMClient:
        return StubLLMClient(responses)
    return _make


@pytest.fixture(autouse=True)
def _register_tools():
    """Ensure tools are registered before each test."""
    # Save and restore tools to avoid pollution between tests
    saved = dict(ToolRegistry._tools)
    # Force import of tool modules to trigger registration
    import agent.tools  # noqa: F401
    yield
    ToolRegistry._tools = saved
