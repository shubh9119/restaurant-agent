"""Tool layer — auto-imports all tool modules to trigger registration."""

from agent.tools import (  # noqa: F401
    menu_tools,
    table_tools,
    customer_tools,
    reservation_tools,
    order_tools,
)
