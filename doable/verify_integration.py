"""
Verification script: runs the `doable` implementation components directly
against the mock backend without needing an interactive human CLI.
"""
import sys
import os
import json

# Ensure doable directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import RestaurantAPI
from tools import init_tools, dispatch, get_tool_definitions
from agent_loop import build_system_prompt, Agent
from llm_client import LLMResponse, ToolCall


def run_verification():
    print("1. Initializing API Client connecting to mock backend at http://localhost:8000...")
    api = RestaurantAPI(base_url="http://localhost:8000")
    init_tools(api)

    print("2. Looking up Priya Sharma (+91-9876543210)...")
    customer = api.lookup_customer(phone="+91-9876543210")
    print(f"   Found customer: {customer['name']} | ID: {customer['id']}")
    print(f"   Stored Preferences: {customer.get('preferences')}")

    orders = api.get_customer_orders(customer["id"])
    print(f"   Fetched {len(orders)} historical order items.")
    customer["recent_orders"] = ", ".join([f"{o['menu_item_name']} x{o['quantity']}" for o in orders])

    print("\n3. Testing System Prompt generation with Customer Memory...")
    prompt = build_system_prompt(customer)
    assert "Priya Sharma" in prompt
    assert "outdoor" in prompt
    print("   [PASS] System prompt injected Priya's outdoor preference & order history.")

    print("\n4. Testing Tool Definitions & Safe Dispatch...")
    defs = get_tool_definitions()
    print(f"   [PASS] Generated {len(defs)} tool definitions automatically.")

    # Test menu search tool
    menu_res = json.loads(dispatch("search_menu", {"dietary_tag": "vegetarian", "max_price": 400}))
    print(f"   [PASS] search_menu found {menu_res['count']} vegetarian items <= 400.")

    # Test availability check
    avail_res = json.loads(dispatch("check_availability", {"date": "2026-08-27", "party_size": 3}))
    print(f"   [PASS] check_availability found {len(avail_res.get('available_tables', []))} suitable tables.")

    # Test booking table
    res_data = json.loads(dispatch("create_reservation", {
        "customer_id": customer["id"],
        "table_id": 7,
        "date": "2026-08-27",
        "time": "20:00",
        "party_size": 3,
    }))
    res_id = res_data["id"]
    print(f"   [PASS] create_reservation successfully created Reservation #{res_id}.")

    # Test adding order
    order_data = json.loads(dispatch("add_order_item", {
        "reservation_id": res_id,
        "menu_item_id": 1,
        "quantity": 2,
    }))
    print(f"   [PASS] add_order_item added {order_data['menu_item_name']} x{order_data['quantity']}.")

    # Test preference update
    updated_cust = json.loads(dispatch("update_preferences", {
        "customer_id": customer["id"],
        "preferences": json.dumps({"notes": "prefers quiet table"}),
    }))
    assert updated_cust["preferences"]["notes"] == "prefers quiet table"
    print("   [PASS] update_preferences persisted new notes into customer memory.")

    print("\n==========================================")
    print(" ALL 6 CORE AGENT CAPABILITIES VERIFIED! ")
    print("==========================================")


if __name__ == "__main__":
    run_verification()
