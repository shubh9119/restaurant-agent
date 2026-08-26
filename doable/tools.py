"""Tool registry with @tool decorator + 8 core tools."""
import inspect
import json
from typing import get_type_hints
from api_client import RestaurantAPI, APIError

# ── Registry ──
_registry = {}
_api: RestaurantAPI = None
TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}


def init_tools(api):
    global _api
    _api = api


def tool(description):
    """Decorator: auto-generates JSON schema from type hints."""
    def decorator(func):
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        properties, required = {}, []
        for name, param in sig.parameters.items():
            properties[name] = {"type": TYPE_MAP.get(hints.get(name, str), "string")}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        _registry[func.__name__] = {
            "func": func,
            "definition": {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": description,
                    "parameters": {"type": "object", "properties": properties, "required": required},
                },
            },
        }
        return func
    return decorator


def get_tool_definitions():
    return [t["definition"] for t in _registry.values()]


def dispatch(tool_name, arguments):
    """Execute a tool safely. Returns JSON string always."""
    if tool_name not in _registry:
        return json.dumps({"error": f"Unknown tool '{tool_name}'. Available: {list(_registry.keys())}"})
    if isinstance(arguments, str):
        try: arguments = json.loads(arguments)
        except: return json.dumps({"error": "Could not parse arguments as JSON"})
    if not isinstance(arguments, dict):
        arguments = {}
    try:
        result = _registry[tool_name]["func"](**arguments)
        return json.dumps(result, default=str)
    except TypeError as e:
        return json.dumps({"error": f"Wrong arguments for {tool_name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"{tool_name} failed: {e}"})


# ── Tools ──

@tool("Get the full restaurant menu")
def get_menu():
    return {"menu_items": _api.get_menu()}


@tool("Search menu by category (starter/main/dessert/beverage), dietary tag, or max price")
def search_menu(category: str = "", dietary_tag: str = "", max_price: float = 0):
    items = [i for i in _api.get_menu() if i.get("available", True)]
    if category:
        items = [i for i in items if i.get("category", "").lower() == category.lower()]
    if dietary_tag:
        items = [i for i in items if dietary_tag.lower() in [t.lower() for t in i.get("tags", [])]]
    if max_price > 0:
        items = [i for i in items if i.get("price", 0) <= max_price]
    return {"results": items, "count": len(items)}


@tool("Check table availability for a date (YYYY-MM-DD) and party size")
def check_availability(date: str, party_size: int):
    try:
        return _api.get_availability(date, party_size)
    except APIError as e:
        return {"error": e.detail}


@tool("Look up a customer by phone or email")
def lookup_customer(phone: str = "", email: str = ""):
    try:
        return _api.lookup_customer(phone=phone or None, email=email or None)
    except APIError as e:
        return {"error": e.detail, "found": False}


@tool("Create a reservation. Time must be HH:MM in 30-min slots (12:00-22:30)")
def create_reservation(customer_id: int, table_id: int, date: str, time: str, party_size: int):
    try:
        return _api.create_reservation(customer_id, table_id, date, time, party_size)
    except APIError as e:
        return {"error": e.detail}


@tool("Cancel a reservation by ID")
def cancel_reservation(reservation_id: int):
    try:
        return _api.cancel_reservation(reservation_id)
    except APIError as e:
        return {"error": e.detail}


@tool("Add a menu item to a reservation's order")
def add_order_item(reservation_id: int, menu_item_id: int, quantity: int = 1):
    try:
        return _api.add_order_item(reservation_id, menu_item_id, quantity)
    except APIError as e:
        return {"error": e.detail}


@tool("Get a customer's order history across all past reservations")
def get_order_history(customer_id: int):
    try:
        orders = _api.get_customer_orders(customer_id)
        return {"orders": orders, "count": len(orders)}
    except APIError as e:
        return {"error": e.detail}
