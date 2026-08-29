"""Interactive CLI for the Restaurant Reception Agent."""
import os
import sys
import argparse
from dotenv import load_dotenv
from api_client import RestaurantAPI, APIError
from tools import init_tools
from llm_client import GeminiClient
from agent_loop import Agent

load_dotenv()


def identify_customer(api):
    print("=" * 60)
    print("  Welcome to The Golden Plate Restaurant!")
    print("=" * 60)
    identifier = input("\nYour phone or email: ").strip()
    if not identifier:
        return None

    # Lookup existing customer
    try:
        if "@" in identifier:
            customer = api.lookup_customer(email=identifier)
        else:
            customer = api.lookup_customer(phone=identifier)
        print(f"\nWelcome back, {customer['name']}!")
        # Load order history for memory
        try:
            orders = api.get_customer_orders(customer["id"])
            if orders:
                customer["recent_orders"] = ", ".join(
                    [f"{o.get('menu_item_name', 'Item')} x{o.get('quantity', 1)}" for o in orders[-6:]]
                )
        except: pass
        return customer
    except APIError:
        pass

    # New customer
    print("New customer! Let's create your profile.")
    name = input("Your name: ").strip()
    if not name:
        return None
    try:
        if "@" in identifier:
            return api.create_customer(name=name, phone="", email=identifier)
        else:
            return api.create_customer(name=name, phone=identifier)
    except APIError as e:
        print(f"Could not create profile: {e.detail}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Restaurant AI Agent")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "gemini-3.5-flash"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    api = RestaurantAPI(base_url=args.backend)
    init_tools(api)
    customer_context = identify_customer(api)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not set. Add it to .env file.")
        sys.exit(1)
    llm = GeminiClient(api_key=api_key, model=args.model)

    agent = Agent(llm_client=llm, customer_context=customer_context, verbose=args.verbose)

    print("\n" + "-" * 60)
    print("Ready! Type 'exit' to end.")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("Thank you! See you soon.")
            break
        reply = agent.process_message(user_input)
        print(f"\nAgent: {reply}")


if __name__ == "__main__":
    main()
