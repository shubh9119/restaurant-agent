"""Order management tools."""

from agent.tools.registry import ToolRegistry, tool
from agent.api_client import APIError


@tool("Add a menu item to a reservation's order")
def add_order_item(reservation_id: int, menu_item_id: int, quantity: int = 1) -> dict:
    """Add an item to the order for a reservation.

    Args:
        reservation_id: The reservation ID.
        menu_item_id: The menu item ID to add.
        quantity: Number of this item to add (default 1).

    Returns:
        Order item details or error.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.add_order_item(
            reservation_id=reservation_id,
            menu_item_id=menu_item_id,
            quantity=quantity,
        )
    except APIError as e:
        return {"error": e.detail}


@tool("Get all order items for a reservation")
def get_reservation_orders(reservation_id: int) -> dict:
    """List all items ordered on a reservation.

    Args:
        reservation_id: The reservation ID.

    Returns:
        List of order items with quantities and prices.
    """
    api = ToolRegistry.get_api_client()
    try:
        orders = api.get_reservation_orders(reservation_id)
        return {"orders": orders, "count": len(orders)}
    except APIError as e:
        return {"error": e.detail}


@tool("Remove an order item from a reservation")
def remove_order_item(reservation_id: int, order_id: int) -> dict:
    """Remove a specific item from a reservation's order.

    Args:
        reservation_id: The reservation ID.
        order_id: The specific order item ID to remove.

    Returns:
        Confirmation or error.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.remove_order_item(
            reservation_id=reservation_id,
            order_id=order_id,
        )
    except APIError as e:
        return {"error": e.detail}


@tool("Get a customer's complete order history across all reservations")
def get_customer_order_history(customer_id: int) -> dict:
    """Get all past orders for a customer.

    Args:
        customer_id: The customer's ID.

    Returns:
        List of all order items from all reservations.
    """
    api = ToolRegistry.get_api_client()
    try:
        orders = api.get_customer_orders(customer_id)
        return {"orders": orders, "count": len(orders)}
    except APIError as e:
        return {"error": e.detail}
