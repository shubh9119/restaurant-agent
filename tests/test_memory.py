"""Tests for customer memory — load, save, identify."""

import pytest
from agent.memory import CustomerMemory
from agent.api_client import APIError


class TestCustomerMemory:
    """Tests for the CustomerMemory manager."""

    def test_identify_existing_customer_by_phone(self, mock_api):
        memory = CustomerMemory(mock_api)
        result = memory.identify_customer(phone="+91-9876543210")
        assert result is not None
        assert result["name"] == "Priya Sharma"

    def test_identify_existing_customer_by_email(self, mock_api):
        memory = CustomerMemory(mock_api)
        result = memory.identify_customer(email="priya@example.com")
        assert result is not None
        assert result["name"] == "Priya Sharma"

    def test_identify_nonexistent_customer(self, mock_api):
        memory = CustomerMemory(mock_api)
        result = memory.identify_customer(phone="+00-0000000000")
        assert result is None

    def test_load_context_includes_preferences(self, mock_api):
        memory = CustomerMemory(mock_api)
        context = memory.load_context(customer_id=1)
        assert context["name"] == "Priya Sharma"
        assert context["preferences"]["seating_preference"] == "outdoor"
        assert "vegetarian" in context["preferences"]["dietary_restrictions"]

    def test_load_context_includes_recent_orders(self, mock_api):
        memory = CustomerMemory(mock_api)
        context = memory.load_context(customer_id=1)
        assert context["recent_orders"] is not None
        assert "Paneer Tikka" in context["recent_orders"]
        assert "Dal Makhani" in context["recent_orders"]

    def test_save_preference(self, mock_api):
        memory = CustomerMemory(mock_api)
        result = memory.save_preference(1, "notes", "likes mild spice")
        assert result["preferences"]["notes"] == "likes mild spice"

    def test_save_preferences_merges(self, mock_api):
        memory = CustomerMemory(mock_api)
        memory.save_preferences(1, {"notes": "mild spice", "favorite_time": "20:00"})
        # Original preferences should still be there
        customer = mock_api.get_customer(1)
        assert customer["preferences"]["seating_preference"] == "outdoor"
        assert customer["preferences"]["notes"] == "mild spice"
        assert customer["preferences"]["favorite_time"] == "20:00"
