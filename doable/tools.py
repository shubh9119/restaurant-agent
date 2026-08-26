"""
FILE 2: tools.py — Tool registry + all tools in ONE file.
Write this SECOND (15 min). This is your STAR piece.

WHY THIS DESIGN:
- Decorator pattern (@tool) = evaluators see you know metaprogramming
- Auto-generates JSON schema from Python type hints = no manual schema writing
- dispatch() handles 3 failure modes: unknown tool, bad args, execution error
- All tools in one file = easy to read, no import gymnastics
- Adding a new tool = write ONE function with @tool decorator

KEY PATTERN TO MEMORIZE:
    @tool("description of what this tool does")
    def my_tool(param1: str, param2: int = 0) -> dict:
        api = _api  # module-level API client reference
        return api.some_method(param1, param2)
"""

import inspect
import json
from typing import get_type_hints
from api_client import RestaurantAPI, APIError


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL REGISTRY — The core pattern (~30 lines)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_registry: dict = {}    # name → {func, definition}
_api: RestaurantAPI = None  # set once at startup

TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}


def init_tools(api: RestaurantAPI):
    """Call once at startup to inject the API client."""
    global _api
    _api = api


def tool(description: str):
    """Decorator: registers a function as an LLM-callable tool.

    Auto-generates JSON schema from the function's type hints.
    Required params = no default value. Optional = has default.
    """
    def decorator(func):
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            py_type = hints.get(name, str)
            properties[name] = {"type": TYPE_MAP.get(py_type, "string")}
            if param.default is inspect.Parameter.empty:
                required.append(name)

        _registry[func.__name__] = {
            "func": func,
            "definition": {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            },
        }
        return func
    return decorator


def get_tool_definitions() -> list[dict]:
    """Return all tool schemas for the LLM."""
    return [t["definition"] for t in _registry.values()]


def dispatch(tool_name: str, arguments) -> str:
    """Execute a tool by name. Returns JSON string.

    Handles 3 failure modes:
    1. Unknown tool name (LLM hallucinated)
    2. Malformed arguments (bad JSON from LLM)
    3. Execution error (backend returned an error)
    """
    # Guard: unknown tool
    if tool_name not in _registry:
        return json.dumps({"error": f"Unknown tool '{tool_name}'. Available: {list(_registry.keys())}"})

    # Parse string arguments if needed
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return json.dumps({"error": f"Could not parse arguments as JSON"})

    if not isinstance(arguments, dict):
        arguments = {}

    # Execute with error catching
    try:
        result = _registry[tool_name]["func"](**arguments)
        return json.dumps(result, default=str)
    except TypeError as e:
        return json.dumps({"error": f"Wrong arguments for {tool_name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"{tool_name} failed: {e}"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOLS — Each tool is just a function + @tool decorator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@tool("Get the full restaurant menu with all items, prices, and dietary tags")
def get_menu() -> dict:
    return {"menu_items": _api.get_menu()}


@tool("Search menu items by category (starter/main/dessert/beverage), dietary tag (vegetarian/vegan/contains-nuts/contains-dairy), or max price")
def search_menu(category: str = "", dietary_tag: str = "", max_price: float = 0) -> dict:
    items = _api.get_menu()
    results = []
    for item in items:
        if not item.get("available", True):
            continue
        if category and item.get("category", "").lower() != category.lower():
            continue
        if dietary_tag and dietary_tag.lower() not in [t.lower() for t in item.get("tags", [])]:
            continue
        if max_price > 0 and item.get("price", 0) > max_price:
            continue
        results.append(item)
    return {"results": results, "count": len(results)}


@tool("Check table availability for a date (YYYY-MM-DD) and party size. Returns available tables sorted smallest-first.")
def check_availability(date: str, party_size: int) -> dict:
    try:
        return _api.get_availability(date, party_size)
    except APIError as e:
        return {"error": e.detail}


@tool("Look up a customer by phone number or email address")
def lookup_customer(phone: str = "", email: str = "") -> dict:
    try:
        return _api.lookup_customer(
            phone=phone or None,
            email=email or None,
        )
    except APIError as e:
        return {"error": e.detail, "found": False}


@tool("Register a new customer with name and phone (email optional)")
def create_customer(name: str, phone: str, email: str = "") -> dict:
    try:
        return _api.create_customer(name, phone, email or None)
    except APIError as e:
        return {"error": e.detail}


@tool("Create a table reservation. Time must be HH:MM in 30-min slots from 12:00-22:30.")
def create_reservation(customer_id: int, table_id: int, date: str, time: str, party_size: int) -> dict:
    try:
        return _api.create_reservation(customer_id, table_id, date, time, party_size)
    except APIError as e:
        return {"error": e.detail}


@tool("Cancel a reservation by ID. Cannot cancel within 2 hours of slot time.")
def cancel_reservation(reservation_id: int) -> dict:
    try:
        return _api.cancel_reservation(reservation_id)
    except APIError as e:
        return {"error": e.detail}


@tool("Add a menu item to a reservation's order")
def add_order_item(reservation_id: int, menu_item_id: int, quantity: int = 1) -> dict:
    try:
        return _api.add_order_item(reservation_id, menu_item_id, quantity)
    except APIError as e:
        return {"error": e.detail}


@tool("Get all order items for a reservation")
def get_reservation_orders(reservation_id: int) -> dict:
    try:
        orders = _api.get_reservation_orders(reservation_id)
        return {"orders": orders, "count": len(orders)}
    except APIError as e:
        return {"error": e.detail}


@tool("Get a customer's full order history across all past reservations")
def get_customer_order_history(customer_id: int) -> dict:
    try:
        orders = _api.get_customer_orders(customer_id)
        return {"orders": orders, "count": len(orders)}
    except APIError as e:
        return {"error": e.detail}


@tool("Get all reservations for a customer (past and upcoming)")
def get_customer_reservations(customer_id: int) -> dict:
    try:
        reservations = _api.get_customer_reservations(customer_id)
        return {"reservations": reservations, "count": len(reservations)}
    except APIError as e:
        return {"error": e.detail}


@tool("Update customer preferences (seating_preference, dietary_restrictions, favorite_dishes)")
def update_preferences(customer_id: int, preferences: str) -> dict:
    """preferences should be a JSON string like '{"seating_preference": "outdoor"}'"""
    try:
        prefs = json.loads(preferences) if isinstance(preferences, str) else preferences
        return _api.update_preferences(customer_id, prefs)
    except APIError as e:
        return {"error": e.detail}
