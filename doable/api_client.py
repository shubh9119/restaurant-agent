"""HTTP client for the restaurant backend API."""
import httpx


class APIError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class RestaurantAPI:
    def __init__(self, base_url="http://localhost:8000"):
        self.client = httpx.Client(base_url=base_url, timeout=30)

    def _request(self, method, path, **kwargs):
        r = self.client.request(method, path, **kwargs)
        if r.status_code >= 400:
            detail = r.json().get("detail", r.text) if r.text else "Unknown error"
            raise APIError(r.status_code, str(detail))
        return r.json()

    def get_menu(self):
        return self._request("GET", "/menu")

    def get_availability(self, date, party_size):
        return self._request("GET", "/availability", params={"date": date, "party_size": party_size})

    def lookup_customer(self, phone=None, email=None):
        params = {}
        if phone: params["phone"] = phone
        if email: params["email"] = email
        return self._request("GET", "/customers/lookup", params=params)

    def get_customer(self, customer_id):
        return self._request("GET", f"/customers/{customer_id}")

    def create_customer(self, name, phone, email=None):
        body = {"name": name, "phone": phone}
        if email: body["email"] = email
        return self._request("POST", "/customers", json=body)

    def update_preferences(self, customer_id, prefs):
        return self._request("PATCH", f"/customers/{customer_id}/preferences", json=prefs)

    def get_customer_orders(self, customer_id):
        return self._request("GET", f"/customers/{customer_id}/orders")

    def create_reservation(self, customer_id, table_id, date, time, party_size):
        return self._request("POST", "/reservations", json={
            "customer_id": customer_id, "table_id": table_id,
            "date": date, "time": time, "party_size": party_size,
        })

    def cancel_reservation(self, reservation_id):
        return self._request("DELETE", f"/reservations/{reservation_id}")

    def add_order_item(self, reservation_id, menu_item_id, quantity=1):
        return self._request("POST", f"/reservations/{reservation_id}/orders",
                             json={"menu_item_id": menu_item_id, "quantity": quantity})

    def get_reservation_orders(self, reservation_id):
        return self._request("GET", f"/reservations/{reservation_id}/orders")
