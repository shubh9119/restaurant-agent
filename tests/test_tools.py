"""Tests for individual tools — each tested with the MockAPIClient."""

import json
import pytest

from agent.tools.registry import ToolRegistry
from agent.tools.menu_tools import get_menu, search_menu
from agent.tools.table_tools import list_tables, check_availability
from agent.tools.customer_tools import lookup_customer, create_customer, get_customer_profile
from agent.tools.reservation_tools import create_reservation, cancel_reservation, get_customer_reservations
from agent.tools.order_tools import add_order_item, get_reservation_orders, get_customer_order_history


class TestMenuTools:
    """Tests for menu query tools."""

    def test_get_menu_returns_all_items(self, mock_api):
        result = get_menu()
        assert "menu_items" in result
        assert result["total_items"] == 5

    def test_search_menu_by_category(self, mock_api):
        result = search_menu(category="starter")
        assert result["count"] == 2  # Paneer Tikka + Chicken Wings

    def test_search_menu_by_dietary_tag(self, mock_api):
        result = search_menu(dietary_tag="vegetarian")
        # Paneer Tikka, Dal Makhani, Gulab Jamun (Tiramisu is unavailable)
        assert result["count"] == 3

    def test_search_menu_by_max_price(self, mock_api):
        result = search_menu(max_price=300)
        # Gulab Jamun (200) and Veg Spring Rolls... but mock only has specific items
        names = [i["name"] for i in result["results"]]
        assert all(i["price"] <= 300 for i in result["results"])

    def test_search_menu_excludes_unavailable(self, mock_api):
        """Unavailable items (Tiramisu) should not appear in search results."""
        result = search_menu()  # No filters
        names = [i["name"] for i in result["results"]]
        assert "Tiramisu" not in names


class TestTableTools:
    """Tests for table and availability tools."""

    def test_list_tables(self, mock_api):
        result = list_tables()
        assert "tables" in result
        assert len(result["tables"]) == 3

    def test_check_availability(self, mock_api):
        result = check_availability(date="2026-08-27", party_size=3)
        assert "available_tables" in result
        # Tables with capacity >= 3: id 5 (cap 4) and id 7 (cap 4)
        table_ids = [t["table_id"] for t in result["available_tables"]]
        assert 5 in table_ids
        assert 7 in table_ids
        assert 1 not in table_ids  # cap 2, too small


class TestCustomerTools:
    """Tests for customer management tools."""

    def test_lookup_existing_customer(self, mock_api):
        result = lookup_customer(phone="+91-9876543210")
        assert result["name"] == "Priya Sharma"

    def test_lookup_nonexistent_customer(self, mock_api):
        result = lookup_customer(phone="+00-0000000000")
        assert "error" in result
        assert result.get("found") is False

    def test_create_customer(self, mock_api):
        result = create_customer(name="New Person", phone="+91-1111111111")
        assert result["name"] == "New Person"
        assert result["id"] == 99

    def test_get_customer_profile(self, mock_api):
        result = get_customer_profile(customer_id=1)
        assert result["name"] == "Priya Sharma"
        assert "preferences" in result


class TestReservationTools:
    """Tests for reservation management tools."""

    def test_create_reservation(self, mock_api):
        result = create_reservation(
            customer_id=1, table_id=5,
            date="2026-08-27", time="19:00", party_size=3,
        )
        assert result["status"] == "confirmed"
        assert result["table_id"] == 5

    def test_cancel_reservation(self, mock_api):
        # First create one
        res = create_reservation(customer_id=1, table_id=5, date="2026-08-27", time="19:00", party_size=3)
        result = cancel_reservation(reservation_id=res["id"])
        assert "cancelled" in str(result).lower()

    def test_get_customer_reservations(self, mock_api):
        create_reservation(customer_id=1, table_id=5, date="2026-08-27", time="19:00", party_size=3)
        result = get_customer_reservations(customer_id=1)
        assert result["count"] >= 1


class TestOrderTools:
    """Tests for order management tools."""

    def test_add_order_item(self, mock_api):
        # Create a reservation first
        res = mock_api.create_reservation(customer_id=1, table_id=5, date="2026-08-27", time="19:00", party_size=3)
        result = add_order_item(reservation_id=res["id"], menu_item_id=1, quantity=2)
        assert result["quantity"] == 2
        assert result["reservation_id"] == res["id"]

    def test_get_reservation_orders(self, mock_api):
        res = mock_api.create_reservation(customer_id=1, table_id=5, date="2026-08-27", time="19:00", party_size=3)
        mock_api.add_order_item(reservation_id=res["id"], menu_item_id=1, quantity=1)
        result = get_reservation_orders(reservation_id=res["id"])
        assert result["count"] == 1

    def test_get_customer_order_history(self, mock_api):
        result = get_customer_order_history(customer_id=1)
        assert result["count"] == 2  # Paneer Tikka + Dal Makhani from mock
