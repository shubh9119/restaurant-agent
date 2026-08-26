"""
FILE 5: main.py — Interactive CLI Application.
Write this FIFTH (15 min).

WHY THIS DESIGN:
- Single entrypoint to run the agent interactively.
- Identifies the customer upfront (phone or email) -> loads memory (preferences & recent orders).
- If customer is not found, automatically registers them or lets them proceed as a guest.
- Connects API Client -> Tool Registry -> LLM Client -> Agent Loop.
- Supports --verbose mode for reasoning traces.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

from api_client import RestaurantAPI, APIError
from tools import init_tools
from llm_client import GeminiClient, OpenAIClient
from agent_loop import Agent

load_dotenv()


def identify_customer(api: RestaurantAPI) -> dict:
    """Prompt the user for phone/email and load their profile and order history."""
    print("=" * 60)
    print(" 🍽️  Welcome to The Golden Plate Restaurant Reception")
    print("=" * 60)
    identifier = input("\nPlease enter your phone number or email (e.g. +91-9876543210): ").strip()
    if not identifier:
        print("Continuing as Guest.")
        return None

    # Lookup existing customer
    customer = None
    try:
        if "@" in identifier:
            customer = api.lookup_customer(email=identifier)
        else:
            customer = api.lookup_customer(phone=identifier)
    except APIError:
        pass

    if customer:
        print(f"\n✨ Welcome back, {customer['name']}!")
        # Fetch past orders for context
        try:
            orders = api.get_customer_orders(customer["id"])
            if orders:
                recent_summary = [f"{o.get('menu_item_name', 'Item')} x{o.get('quantity', 1)}" for o in orders[-6:]]
                customer["recent_orders"] = ", ".join(recent_summary)
        except Exception:
            pass
        return customer

    # Create new customer if not found
    print(f"I don't have a profile for '{identifier}' yet. Let's create one!")
    name = input("What is your full name? ").strip()
    if not name:
        return None

    try:
        if "@" in identifier:
            new_cust = api.create_customer(name=name, phone="", email=identifier)
        else:
            new_cust = api.create_customer(name=name, phone=identifier)
        print(f"🎉 Created profile for {name}!")
        return new_cust
    except APIError as e:
        print(f"Could not register profile: {e.detail}")
        return None


def main():
    parser = argparse.ArgumentParser(description="AI Restaurant Receptionist CLI")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"), help="Backend URL")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "gemini"), choices=["gemini", "openai"], help="LLM Provider")
    parser.add_argument("--verbose", action="store_true", help="Print reasoning trace and tool calls")
    args = parser.parse_args()

    # 1. Setup API & Tool registry
    api = RestaurantAPI(base_url=args.backend)
    init_tools(api)

    # 2. Identify customer & load memory
    customer_context = identify_customer(api)

    # 3. Setup LLM client
    if args.provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not set in environment or .env file.")
            sys.exit(1)
        llm = GeminiClient(api_key=api_key)
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not set in environment or .env file.")
            sys.exit(1)
        llm = OpenAIClient(api_key=api_key)

    # 4. Initialize Agent
    agent = Agent(llm_client=llm, customer_context=customer_context, verbose=args.verbose)

    print("\n" + "-" * 60)
    print("Receptionist is ready! Type 'exit' or 'quit' to end.")
    print("-" * 60)

    # 5. Multi-turn conversation loop
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("Thank you for reaching out to The Golden Plate! Have a wonderful day. 👋")
            break

        reply = agent.process_message(user_input)
        print(f"\nAgent: {reply}")


if __name__ == "__main__":
    main()
