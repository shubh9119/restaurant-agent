"""Mock restaurant backend — FastAPI app with all endpoints and business rules."""

import copy
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

from mock_backend.models import (
    CustomerCreate, OrderItemCreate, ReservationCreate,
)
from mock_backend.seed_data import (
    TABLES, MENU_ITEMS, CUSTOMERS, RESERVATIONS, ORDERS, NEXT_IDS,
)

app = FastAPI(title="Restaurant API (Mock)", version="1.0.0")

# ── In-memory data store (deep-copied from seed) ───────────────────────────

_tables: list[dict] = copy.deepcopy(TABLES)
_menu: list[dict] = copy.deepcopy(MENU_ITEMS)
_customers: list[dict] = copy.deepcopy(CUSTOMERS)
_reservations: list[dict] = copy.deepcopy(RESERVATIONS)
_orders: list[dict] = copy.deepcopy(ORDERS)
_next: dict[str, int] = copy.deepcopy(NEXT_IDS)

# Valid 30-min time slots from 12:00 to 22:30
VALID_SLOTS: list[str] = []
for h in range(12, 23):
    for m in (0, 30):
        slot = f"{h:02d}:{m:02d}"
        if slot <= "22:30":
            VALID_SLOTS.append(slot)


def _reset_data() -> None:
    """Reset all data to seed values (for testing)."""
    global _tables, _menu, _customers, _reservations, _orders, _next
    _tables = copy.deepcopy(TABLES)
    _menu = copy.deepcopy(MENU_ITEMS)
    _customers = copy.deepcopy(CUSTOMERS)
    _reservations = copy.deepcopy(RESERVATIONS)
    _orders = copy.deepcopy(ORDERS)
    _next = copy.deepcopy(NEXT_IDS)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reseed")
def reseed():
    """Re-seed the database to its initial state."""
    _reset_data()
    return {"status": "reseeded"}


# ── Tables ──────────────────────────────────────────────────────────────────

@app.get("/tables")
def get_tables():
    return _tables


# ── Menu ────────────────────────────────────────────────────────────────────

@app.get("/menu")
def get_menu():
    return _menu


# ── Availability ────────────────────────────────────────────────────────────

@app.get("/availability")
def get_availability(date: str = Query(...), party_size: int = Query(...)):
    """Return tables that fit the party with their available slots."""
    fitting_tables = [t for t in _tables if t["capacity"] >= party_size]
    if not fitting_tables:
        return {"date": date, "party_size": party_size, "available_tables": []}

    # Find which table+slot combos are already booked
    booked: set[tuple[int, str]] = set()
    for r in _reservations:
        if r["date"] == date and r["status"] == "confirmed":
            booked.add((r["table_id"], r["time"]))

    result = []
    for table in fitting_tables:
        free_slots = [s for s in VALID_SLOTS if (table["id"], s) not in booked]
        if free_slots:
            result.append({
                "table_id": table["id"],
                "capacity": table["capacity"],
                "location": table["location"],
                "available_slots": free_slots,
            })

    # Sort by capacity ascending (smart assignment: smallest first)
    result.sort(key=lambda t: t["capacity"])
    return {"date": date, "party_size": party_size, "available_tables": result}


# ── Customers ───────────────────────────────────────────────────────────────

@app.post("/customers", status_code=201)
def create_customer(body: CustomerCreate):
    # Check phone uniqueness
    for c in _customers:
        if c["phone"] == body.phone:
            raise HTTPException(400, f"Customer with phone {body.phone} already exists.")
    cust = {
        "id": _next["customer"],
        "name": body.name,
        "phone": body.phone,
        "email": body.email,
        "preferences": {},
    }
    _next["customer"] += 1
    _customers.append(cust)
    return cust


@app.get("/customers/lookup")
def lookup_customer(
    phone: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
):
    for c in _customers:
        if phone and c["phone"] == phone:
            return c
        if email and c.get("email") == email:
            return c
    raise HTTPException(404, "Customer not found.")


@app.get("/customers/{customer_id}")
def get_customer(customer_id: int):
    for c in _customers:
        if c["id"] == customer_id:
            return c
    raise HTTPException(404, f"Customer {customer_id} not found.")


@app.patch("/customers/{customer_id}/preferences")
def update_preferences(customer_id: int, prefs: dict):
    for c in _customers:
        if c["id"] == customer_id:
            c["preferences"].update(prefs)  # shallow merge
            return c
    raise HTTPException(404, f"Customer {customer_id} not found.")


@app.get("/customers/{customer_id}/reservations")
def get_customer_reservations(customer_id: int):
    return [r for r in _reservations if r["customer_id"] == customer_id]


@app.get("/customers/{customer_id}/orders")
def get_customer_orders(customer_id: int):
    cust_res_ids = {r["id"] for r in _reservations if r["customer_id"] == customer_id}
    return [o for o in _orders if o["reservation_id"] in cust_res_ids]


# ── Reservations ────────────────────────────────────────────────────────────

@app.post("/reservations", status_code=201)
def create_reservation(body: ReservationCreate):
    # Validate table exists
    table = next((t for t in _tables if t["id"] == body.table_id), None)
    if not table:
        raise HTTPException(400, f"Table {body.table_id} does not exist.")

    # Validate capacity
    if body.party_size > table["capacity"]:
        raise HTTPException(
            400,
            f"Party size {body.party_size} exceeds table {body.table_id} capacity of {table['capacity']}.",
        )

    # Validate time slot
    if body.time not in VALID_SLOTS:
        raise HTTPException(
            400,
            f"Invalid time slot '{body.time}'. Must be a 30-minute increment from 12:00 to 22:30.",
        )

    # Check for double-booking
    for r in _reservations:
        if (
            r["table_id"] == body.table_id
            and r["date"] == body.date
            and r["time"] == body.time
            and r["status"] == "confirmed"
        ):
            raise HTTPException(
                409,
                f"Table {body.table_id} is already booked at {body.time} on {body.date}.",
            )

    # Validate customer exists
    cust = next((c for c in _customers if c["id"] == body.customer_id), None)
    if not cust:
        raise HTTPException(400, f"Customer {body.customer_id} does not exist.")

    reservation = {
        "id": _next["reservation"],
        "customer_id": body.customer_id,
        "table_id": body.table_id,
        "date": body.date,
        "time": body.time,
        "party_size": body.party_size,
        "status": "confirmed",
    }
    _next["reservation"] += 1
    _reservations.append(reservation)
    return reservation


@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: int):
    for r in _reservations:
        if r["id"] == reservation_id:
            return r
    raise HTTPException(404, f"Reservation {reservation_id} not found.")


@app.delete("/reservations/{reservation_id}")
def cancel_reservation(reservation_id: int):
    for r in _reservations:
        if r["id"] == reservation_id:
            if r["status"] != "confirmed":
                raise HTTPException(400, f"Reservation is already {r['status']}.")

            # Check 2-hour window
            slot_dt = datetime.strptime(f"{r['date']} {r['time']}", "%Y-%m-%d %H:%M")
            if datetime.now() > slot_dt - timedelta(hours=2):
                raise HTTPException(
                    400,
                    "Cannot cancel within 2 hours of the reservation time.",
                )

            r["status"] = "cancelled"
            return {"message": "Reservation cancelled.", "reservation": r}
    raise HTTPException(404, f"Reservation {reservation_id} not found.")


# ── Orders ──────────────────────────────────────────────────────────────────

@app.post("/reservations/{reservation_id}/orders", status_code=201)
def add_order_item(reservation_id: int, body: OrderItemCreate):
    # Find reservation
    res = next((r for r in _reservations if r["id"] == reservation_id), None)
    if not res:
        raise HTTPException(404, f"Reservation {reservation_id} not found.")

    if res["status"] != "confirmed":
        raise HTTPException(400, f"Cannot add orders to a {res['status']} reservation.")

    # Check slot hasn't passed
    slot_dt = datetime.strptime(f"{res['date']} {res['time']}", "%Y-%m-%d %H:%M")
    if datetime.now() > slot_dt:
        raise HTTPException(400, "Cannot modify orders after the reservation time has passed.")

    # Validate menu item
    item = next((m for m in _menu if m["id"] == body.menu_item_id), None)
    if not item:
        raise HTTPException(400, f"Menu item {body.menu_item_id} does not exist.")
    if not item.get("available", True):
        raise HTTPException(400, f"Menu item '{item['name']}' is currently unavailable.")

    order = {
        "id": _next["order"],
        "reservation_id": reservation_id,
        "menu_item_id": body.menu_item_id,
        "menu_item_name": item["name"],
        "quantity": body.quantity,
        "price": item["price"],
    }
    _next["order"] += 1
    _orders.append(order)
    return order


@app.get("/reservations/{reservation_id}/orders")
def get_reservation_orders(reservation_id: int):
    # Verify reservation exists
    res = next((r for r in _reservations if r["id"] == reservation_id), None)
    if not res:
        raise HTTPException(404, f"Reservation {reservation_id} not found.")
    return [o for o in _orders if o["reservation_id"] == reservation_id]


@app.delete("/reservations/{reservation_id}/orders/{order_id}")
def remove_order_item(reservation_id: int, order_id: int):
    res = next((r for r in _reservations if r["id"] == reservation_id), None)
    if not res:
        raise HTTPException(404, f"Reservation {reservation_id} not found.")

    if res["status"] != "confirmed":
        raise HTTPException(400, f"Cannot modify orders on a {res['status']} reservation.")

    slot_dt = datetime.strptime(f"{res['date']} {res['time']}", "%Y-%m-%d %H:%M")
    if datetime.now() > slot_dt:
        raise HTTPException(400, "Cannot modify orders after the reservation time has passed.")

    for i, o in enumerate(_orders):
        if o["id"] == order_id and o["reservation_id"] == reservation_id:
            removed = _orders.pop(i)
            return {"message": "Order item removed.", "order": removed}

    raise HTTPException(404, f"Order item {order_id} not found on reservation {reservation_id}.")


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
