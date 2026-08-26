"""Reservation management tools."""

from agent.tools.registry import ToolRegistry, tool
from agent.api_client import APIError


@tool("Create a new table reservation")
def create_reservation(customer_id: int, table_id: int, date: str, time: str, party_size: int) -> dict:
    """Book a table for a customer.

    Args:
        customer_id: ID of the customer making the reservation.
        table_id: ID of the table to book.
        date: Date in YYYY-MM-DD format.
        time: Time in HH:MM format (must be a 30-minute increment between 12:00 and 22:30).
        party_size: Number of guests.

    Returns:
        Reservation details with ID, or error message.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.create_reservation(
            customer_id=customer_id,
            table_id=table_id,
            date=date,
            time=time,
            party_size=party_size,
        )
    except APIError as e:
        return {"error": e.detail}


@tool("Get details of a specific reservation")
def get_reservation(reservation_id: int) -> dict:
    """Retrieve reservation details.

    Args:
        reservation_id: The reservation ID.

    Returns:
        Reservation details including status.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.get_reservation(reservation_id)
    except APIError as e:
        return {"error": e.detail}


@tool("Cancel an existing reservation (cannot cancel within 2 hours of the slot)")
def cancel_reservation(reservation_id: int) -> dict:
    """Cancel a reservation.

    Args:
        reservation_id: The reservation ID to cancel.

    Returns:
        Cancellation confirmation or error.
    """
    api = ToolRegistry.get_api_client()
    try:
        return api.cancel_reservation(reservation_id)
    except APIError as e:
        return {"error": e.detail}


@tool("List all reservations for a customer (past and upcoming)")
def get_customer_reservations(customer_id: int) -> dict:
    """Get all reservations for a customer.

    Args:
        customer_id: The customer's ID.

    Returns:
        List of reservations with statuses.
    """
    api = ToolRegistry.get_api_client()
    try:
        reservations = api.get_customer_reservations(customer_id)
        return {"reservations": reservations, "count": len(reservations)}
    except APIError as e:
        return {"error": e.detail}
