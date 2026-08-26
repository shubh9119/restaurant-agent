"""Seed data for the mock restaurant backend.

8 tables, 12 menu items, 3 customers (including Priya Sharma with history).
"""

TABLES = [
    {"id": 1, "capacity": 2, "location": "indoor"},
    {"id": 2, "capacity": 2, "location": "indoor"},
    {"id": 3, "capacity": 4, "location": "indoor"},
    {"id": 4, "capacity": 4, "location": "indoor"},
    {"id": 5, "capacity": 4, "location": "outdoor"},
    {"id": 6, "capacity": 6, "location": "outdoor"},
    {"id": 7, "capacity": 4, "location": "outdoor"},
    {"id": 8, "capacity": 8, "location": "indoor"},
]

MENU_ITEMS = [
    # Starters
    {"id": 1, "name": "Paneer Tikka", "category": "starter", "price": 350.0,
     "tags": ["vegetarian"], "available": True},
    {"id": 2, "name": "Chicken Wings", "category": "starter", "price": 450.0,
     "tags": [], "available": True},
    {"id": 3, "name": "Veg Spring Rolls", "category": "starter", "price": 250.0,
     "tags": ["vegan"], "available": True},
    {"id": 4, "name": "Mixed Nuts Platter", "category": "starter", "price": 300.0,
     "tags": ["vegetarian", "contains-nuts"], "available": True},
    # Mains
    {"id": 5, "name": "Dal Makhani", "category": "main", "price": 400.0,
     "tags": ["vegetarian", "contains-dairy"], "available": True},
    {"id": 6, "name": "Butter Chicken", "category": "main", "price": 550.0,
     "tags": ["contains-dairy"], "available": True},
    {"id": 7, "name": "Grilled Salmon", "category": "main", "price": 650.0,
     "tags": [], "available": True},
    {"id": 8, "name": "Mushroom Risotto", "category": "main", "price": 500.0,
     "tags": ["vegetarian", "contains-dairy"], "available": True},
    # Desserts
    {"id": 9, "name": "Gulab Jamun", "category": "dessert", "price": 200.0,
     "tags": ["vegetarian", "contains-dairy"], "available": True},
    {"id": 10, "name": "Tiramisu", "category": "dessert", "price": 350.0,
     "tags": ["vegetarian", "contains-nuts", "contains-dairy"], "available": True},
    {"id": 11, "name": "Fruit Sorbet", "category": "dessert", "price": 180.0,
     "tags": ["vegan"], "available": True},
    # Beverages
    {"id": 12, "name": "Mango Lassi", "category": "beverage", "price": 150.0,
     "tags": ["vegetarian", "contains-dairy"], "available": True},
]

CUSTOMERS = [
    {
        "id": 1,
        "name": "Priya Sharma",
        "phone": "+91-9876543210",
        "email": "priya@example.com",
        "preferences": {
            "seating_preference": "outdoor",
            "dietary_restrictions": ["vegetarian"],
            "favorite_dishes": ["paneer tikka", "dal makhani", "roti"],
        },
    },
    {
        "id": 2,
        "name": "Rahul Verma",
        "phone": "+91-9123456789",
        "email": "rahul@example.com",
        "preferences": {},
    },
    {
        "id": 3,
        "name": "Sarah Johnson",
        "phone": "+1-5551234567",
        "email": "sarah@example.com",
        "preferences": {
            "dietary_restrictions": ["no-nuts"],
            "seating_preference": "indoor",
        },
    },
]

# Past reservations for Priya (completed) so she has order history
RESERVATIONS = [
    {
        "id": 1,
        "customer_id": 1,
        "table_id": 5,
        "date": "2026-08-20",
        "time": "19:00",
        "party_size": 2,
        "status": "completed",
    },
    {
        "id": 2,
        "customer_id": 1,
        "table_id": 7,
        "date": "2026-08-23",
        "time": "20:00",
        "party_size": 3,
        "status": "completed",
    },
]

# Past orders for Priya's completed reservations
ORDERS = [
    # Reservation 1 orders
    {"id": 1, "reservation_id": 1, "menu_item_id": 1, "menu_item_name": "Paneer Tikka", "quantity": 1, "price": 350.0},
    {"id": 2, "reservation_id": 1, "menu_item_id": 5, "menu_item_name": "Dal Makhani", "quantity": 1, "price": 400.0},
    # Reservation 2 orders
    {"id": 3, "reservation_id": 2, "menu_item_id": 5, "menu_item_name": "Dal Makhani", "quantity": 2, "price": 400.0},
    {"id": 4, "reservation_id": 2, "menu_item_id": 9, "menu_item_name": "Gulab Jamun", "quantity": 1, "price": 200.0},
]

# Auto-increment counters
NEXT_IDS = {
    "customer": 4,
    "reservation": 3,
    "order": 5,
}
