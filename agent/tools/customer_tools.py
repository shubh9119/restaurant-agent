"""Customer lookup and management tools."""

from agent.tools.registry import ToolRegistry, tool
from agent.api_client import APIError


@tool("Look up an existing customer by phone number or email")
def lookup_customer(phone: str = "", email: str = "") -> dict:
    """Find a customer in the system.

    Args:
        phone: Customer phone number.
        email: Customer email address.

    Returns:
        Customer details including preferences, or error if not found.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.lookup_customer(
            phone=phone if phone else None,
            email=email if email else None,
        )
    except APIError as e:
        return {"error": e.detail, "found": False}


@tool("Register a new customer")
def create_customer(name: str, phone: str, email: str = "") -> dict:
    """Create a new customer record.

    Args:
        name: Customer full name.
        phone: Customer phone number.
        email: Customer email (optional).

    Returns:
        Newly created customer record.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.create_customer(name=name, phone=phone, email=email if email else None)
    except APIError as e:
        return {"error": e.detail}


@tool("Get full customer profile including preferences and history")
def get_customer_profile(customer_id: int) -> dict:
    """Get detailed customer information.

    Args:
        customer_id: The customer's ID.

    Returns:
        Customer profile with preferences.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.get_customer(customer_id)
    except APIError as e:
        return {"error": e.detail}


@tool("Update a customer's stored preferences (seating, dietary, favorites, notes)")
def update_customer_preferences(customer_id: int, preferences: dict) -> dict:
    """Save or update customer preferences. Shallow-merges with existing.

    Args:
        customer_id: The customer's ID.
        preferences: Preference key-value pairs to save. Keys can include: seating_preference, dietary_restrictions, favorite_dishes, notes.

    Returns:
        Updated customer record.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.update_preferences(customer_id, preferences)
    except APIError as e:
        return {"error": e.detail}
