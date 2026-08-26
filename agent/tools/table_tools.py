"""Table and availability tools."""

from agent.tools.registry import ToolRegistry, tool
from agent.api_client import APIError


@tool("List all tables with their capacity and location (indoor/outdoor)")
def list_tables() -> dict:
    """Get all restaurant tables.

    Returns:
        List of tables with id, capacity, and location.
    """
    api = ToolRegistry.get_api_client()
    tables = api.get_tables()
    return {"tables": tables}


@tool("Check table availability for a given date and party size. Returns available tables sorted by capacity (smallest first) with their open time slots.")
def check_availability(date: str, party_size: int) -> dict:
    """Check which tables are available on a date for a party size.

    Args:
        date: Date in YYYY-MM-DD format.
        party_size: Number of guests.

    Returns:
        Available tables with their open time slots.
    """
    api = ToolRegistry.get_api_client()
    try:
        result = api.get_availability(date=date, party_size=party_size)
        return result
    except APIError as e:
        return {"error": e.detail}
