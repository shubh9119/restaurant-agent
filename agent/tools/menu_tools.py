"""Menu query tools."""

from agent.tools.registry import ToolRegistry, tool
from agent.api_client import APIError


@tool("Get the full restaurant menu with all items, prices, and dietary tags")
def get_menu() -> dict:
    """Retrieve the complete menu.

    Returns:
        Full menu with items grouped by availability.
    """
    api = ToolRegistry.get_api_client()
    items = api.get_menu()
    return {"menu_items": items, "total_items": len(items)}


@tool("Search menu items by category, dietary tags, or maximum price")
def search_menu(category: str = "", dietary_tag: str = "", max_price: float = 0) -> dict:
    """Search and filter menu items.

    Args:
        category: Filter by category — one of: starter, main, dessert, beverage. Leave empty for all.
        dietary_tag: Filter by dietary tag — e.g. vegetarian, vegan, contains-nuts, contains-dairy. Leave empty for all.
        max_price: Maximum price. Use 0 for no limit.

    Returns:
        Matching menu items.
    """
    api = ToolRegistry.get_api_client()
    items = api.get_menu()

    filtered = []
    for item in items:
        if not item.get("available", True):
            continue
        if category and item.get("category", "").lower() != category.lower():
            continue
        if dietary_tag and dietary_tag.lower() not in [t.lower() for t in item.get("tags", [])]:
            continue
        if max_price > 0 and item.get("price", 0) > max_price:
            continue
        filtered.append(item)

    return {"results": filtered, "count": len(filtered)}
