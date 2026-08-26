"""Typed HTTP client for the Restaurant backend API."""

import httpx
from typing import Any, Optional


class APIError(Exception):
    """Raised when the backend returns an HTTP error (4xx / 5xx)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API Error {status_code}: {detail}")


class RestaurantAPIClient:
    """Synchronous HTTP client for the restaurant REST API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request and raise APIError on failure."""
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(resp.status_code, str(detail))
        if resp.status_code == 204:
            return None
        return resp.json()

    # ── Tables ──────────────────────────────────────────────────────────

    def get_tables(self) -> list[dict]:
        """Get all restaurant tables."""
        return self._request("GET", "/tables")

    # ── Menu ────────────────────────────────────────────────────────────

    def get_menu(self) -> list[dict]:
        """Get the full menu."""
        return self._request("GET", "/menu")

    # ── Availability ────────────────────────────────────────────────────

    def get_availability(self, date: str, party_size: int) -> dict:
        """Check table availability for a date and party size."""
        return self._request("GET", "/availability", params={"date": date, "party_size": party_size})

    # ── Customers ───────────────────────────────────────────────────────

    def lookup_customer(self, phone: Optional[str] = None, email: Optional[str] = None) -> dict:
        """Find a customer by phone or email."""
        params: dict[str, str] = {}
        if phone:
            params["phone"] = phone
        if email:
            params["email"] = email
        return self._request("GET", "/customers/lookup", params=params)

    def get_customer(self, customer_id: int) -> dict:
        """Get customer details by ID."""
        return self._request("GET", f"/customers/{customer_id}")

    def create_customer(self, name: str, phone: str, email: Optional[str] = None) -> dict:
        """Create a new customer."""
        body: dict[str, Any] = {"name": name, "phone": phone}
        if email:
            body["email"] = email
        return self._request("POST", "/customers", json=body)

    def update_preferences(self, customer_id: int, preferences: dict) -> dict:
        """Shallow-merge preferences into customer's stored preferences."""
        return self._request("PATCH", f"/customers/{customer_id}/preferences", json=preferences)

    def get_customer_reservations(self, customer_id: int) -> list[dict]:
        """Get all reservations for a customer."""
        return self._request("GET", f"/customers/{customer_id}/reservations")

    def get_customer_orders(self, customer_id: int) -> list[dict]:
        """Get all order items across all of a customer's reservations."""
        return self._request("GET", f"/customers/{customer_id}/orders")

    # ── Reservations ────────────────────────────────────────────────────

    def create_reservation(
        self, customer_id: int, table_id: int, date: str, time: str, party_size: int
    ) -> dict:
        """Create a table reservation."""
        return self._request("POST", "/reservations", json={
            "customer_id": customer_id,
            "table_id": table_id,
            "date": date,
            "time": time,
            "party_size": party_size,
        })

    def get_reservation(self, reservation_id: int) -> dict:
        """Get reservation details."""
        return self._request("GET", f"/reservations/{reservation_id}")

    def cancel_reservation(self, reservation_id: int) -> dict:
        """Cancel a reservation."""
        return self._request("DELETE", f"/reservations/{reservation_id}")

    # ── Orders ──────────────────────────────────────────────────────────

    def add_order_item(self, reservation_id: int, menu_item_id: int, quantity: int = 1) -> dict:
        """Add an item to a reservation's order."""
        return self._request("POST", f"/reservations/{reservation_id}/orders", json={
            "menu_item_id": menu_item_id,
            "quantity": quantity,
        })

    def get_reservation_orders(self, reservation_id: int) -> list[dict]:
        """Get all order items for a reservation."""
        return self._request("GET", f"/reservations/{reservation_id}/orders")

    def remove_order_item(self, reservation_id: int, order_id: int) -> dict:
        """Remove an order item from a reservation."""
        return self._request("DELETE", f"/reservations/{reservation_id}/orders/{order_id}")

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
