"""Customer memory — loads & persists preferences via the backend."""

from typing import Optional
from agent.api_client import RestaurantAPIClient, APIError


class CustomerMemory:
    """Manages durable customer memory through the backend's preferences API.

    Durable state (preferences) is persisted in the backend.
    In-conversation state (history) lives in the agent loop.
    """

    def __init__(self, api_client: RestaurantAPIClient):
        self.api = api_client

    def identify_customer(
        self, phone: Optional[str] = None, email: Optional[str] = None
    ) -> Optional[dict]:
        """Look up a customer by phone or email.

        Returns:
            Customer dict if found, None otherwise.
        """
        try:
            return self.api.lookup_customer(phone=phone, email=email)
        except APIError:
            return None

    def load_context(self, customer_id: int) -> dict:
        """Load full customer context: profile + preferences + recent orders.

        Args:
            customer_id: The customer's database ID.

        Returns:
            Dict with keys: id, name, phone, email, preferences, recent_orders.
        """
        customer = self.api.get_customer(customer_id)
        context: dict = {
            "id": customer["id"],
            "name": customer["name"],
            "phone": customer["phone"],
            "email": customer.get("email"),
            "preferences": customer.get("preferences", {}),
        }

        # Load recent orders for context
        try:
            orders = self.api.get_customer_orders(customer_id)
            if orders:
                recent = []
                for order in orders[-10:]:  # Last 10 items
                    name = order.get("menu_item_name", "unknown")
                    qty = order.get("quantity", 1)
                    recent.append(f"{name} x{qty}")
                context["recent_orders"] = ", ".join(recent)
            else:
                context["recent_orders"] = None
        except APIError:
            context["recent_orders"] = None

        return context

    def save_preference(self, customer_id: int, key: str, value: object) -> dict:
        """Save a single preference (shallow-merge).

        Args:
            customer_id: The customer's database ID.
            key: Preference key (e.g., 'seating_preference').
            value: Preference value.

        Returns:
            Updated customer record.
        """
        return self.api.update_preferences(customer_id, {key: value})

    def save_preferences(self, customer_id: int, preferences: dict) -> dict:
        """Save multiple preferences (shallow-merge).

        Args:
            customer_id: The customer's database ID.
            preferences: Dict of preference key-value pairs.

        Returns:
            Updated customer record.
        """
        return self.api.update_preferences(customer_id, preferences)
