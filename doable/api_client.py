"""
FILE 1: api_client.py — HTTP wrapper for the restaurant backend.
Write this FIRST (10 min). It's just plumbing.

WHY THIS DESIGN:
- One class, one responsibility: talk to the backend.
- Every method is a one-liner that calls _request().
- _request() handles ALL error checking in one place.
- APIError carries status_code + detail so tools can report errors to the LLM.
"""

import httpx


class APIError(Exception):
    """Raised when the backend returns 4xx/5xx."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class RestaurantAPI:
    """Thin HTTP client — one method per endpoint."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.client = httpx.Client(base_url=base_url, timeout=30)

    def _request(self, method: str, path: str, **kwargs):
        """Central request method. Raises APIError on failure."""
        r = self.client.request(method, path, **kwargs)
        if r.status_code >= 400:
            detail = r.json().get("detail", r.text) if r.text else "Unknown error"
            raise APIError(r.status_code, str(detail))
        return r.json()

    # ── Every endpoint as a one-liner ──
    def get_tables(self):
        return self._request("GET", "/tables")

    def get_menu(self):
        return self._request("GET", "/menu")

    def get_availability(self, date: str, party_size: int):
        return self._request("GET", "/availability", params={"date": date, "party_size": party_size})

    def lookup_customer(self, phone: str = None, email: str = None):
        params = {}
        if phone: params["phone"] = phone
        if email: params["email"] = email
        return self._request("GET", "/customers/lookup", params=params)

    def get_customer(self, customer_id: int):
        return self._request("GET", f"/customers/{customer_id}")

    def create_customer(self, name: str, phone: str, email: str = None):
        body = {"name": name, "phone": phone}
        if email: body["email"] = email
        return self._request("POST", "/customers", json=body)

    def update_preferences(self, customer_id: int, prefs: dict):
        return self._request("PATCH", f"/customers/{customer_id}/preferences", json=prefs)

    def get_customer_reservations(self, customer_id: int):
        return self._request("GET", f"/customers/{customer_id}/reservations")

    def get_customer_orders(self, customer_id: int):
        return self._request("GET", f"/customers/{customer_id}/orders")

    def create_reservation(self, customer_id: int, table_id: int, date: str, time: str, party_size: int):
        return self._request("POST", "/reservations", json={
            "customer_id": customer_id, "table_id": table_id,
            "date": date, "time": time, "party_size": party_size,
        })

    def get_reservation(self, reservation_id: int):
        return self._request("GET", f"/reservations/{reservation_id}")

    def cancel_reservation(self, reservation_id: int):
        return self._request("DELETE", f"/reservations/{reservation_id}")

    def add_order_item(self, reservation_id: int, menu_item_id: int, quantity: int = 1):
        return self._request("POST", f"/reservations/{reservation_id}/orders",
                             json={"menu_item_id": menu_item_id, "quantity": quantity})

    def get_reservation_orders(self, reservation_id: int):
        return self._request("GET", f"/reservations/{reservation_id}/orders")

    def remove_order_item(self, reservation_id: int, order_id: int):
        return self._request("DELETE", f"/reservations/{reservation_id}/orders/{order_id}")
