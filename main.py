#!/usr/bin/env python3
"""Restaurant Reception Agent — Interactive CLI.

Usage:
    python main.py                          # Uses Gemini (default)
    python main.py --provider openai        # Uses OpenAI
    python main.py --provider ollama        # Uses Ollama (local)
    python main.py --verbose                # Show reasoning trace
"""

import argparse
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent.config import Config
from agent.api_client import RestaurantAPIClient, APIError
from agent.llm_client import create_llm_client
from agent.agent_loop import AgentLoop
from agent.memory import CustomerMemory
from agent.tools.registry import ToolRegistry

# Import tools to trigger registration via decorators
import agent.tools  # noqa: F401

console = Console()


def identify_customer(memory: CustomerMemory) -> dict | None:
    """Interactive customer identification flow.

    Asks for phone or email, looks up or creates the customer.
    Returns customer context dict or None.
    """
    console.print(
        Panel(
            "[bold]Welcome to The Golden Plate! 🍽️[/bold]\n"
            "I'm your AI receptionist. Let me look you up first.",
            style="green",
        )
    )

    # Get identifier
    identifier = console.input("\n[bold cyan]Your phone or email:[/bold cyan] ").strip()
    if not identifier:
        console.print("[yellow]No identifier provided. Continuing as a guest.[/yellow]")
        return None

    # Determine if phone or email
    is_email = "@" in identifier
    customer = memory.identify_customer(
        email=identifier if is_email else None,
        phone=identifier if not is_email else None,
    )

    if customer:
        # Returning customer → load full context
        context = memory.load_context(customer["id"])
        console.print(f"\n[green]Welcome back, {context['name']}! ✨[/green]")
        if context.get("preferences"):
            prefs = context["preferences"]
            details = []
            if prefs.get("seating_preference"):
                details.append(f"Seating: {prefs['seating_preference']}")
            if prefs.get("dietary_restrictions"):
                details.append(f"Dietary: {', '.join(prefs['dietary_restrictions'])}")
            if details:
                console.print(f"[dim]  Remembered: {' | '.join(details)}[/dim]")
        return context

    # New customer
    console.print("[yellow]I don't have you on file yet. Let me create your profile.[/yellow]")
    name = console.input("[bold cyan]Your name:[/bold cyan] ").strip()
    if not name:
        console.print("[yellow]Name is required. Continuing as a guest.[/yellow]")
        return None

    try:
        api = memory.api
        if is_email:
            new_cust = api.create_customer(name=name, phone="", email=identifier)
        else:
            new_cust = api.create_customer(name=name, phone=identifier)
        context = memory.load_context(new_cust["id"])
        console.print(f"\n[green]Nice to meet you, {name}! You're all set. 🎉[/green]")
        return context
    except APIError as e:
        console.print(f"[red]Could not create profile: {e.detail}[/red]")
        return None


def main() -> None:
    """Run the interactive CLI agent."""
    parser = argparse.ArgumentParser(description="Restaurant Reception Agent CLI")
    parser.add_argument("--provider", default=Config.LLM_PROVIDER, choices=["gemini", "openai", "ollama"],
                        help="LLM provider (default: gemini)")
    parser.add_argument("--model", default=Config.LLM_MODEL, help="Model name")
    parser.add_argument("--verbose", action="store_true", default=Config.VERBOSE,
                        help="Show reasoning trace")
    parser.add_argument("--backend-url", default=Config.BACKEND_URL, help="Backend API URL")
    args = parser.parse_args()

    # Initialise components
    api_client = RestaurantAPIClient(base_url=args.backend_url)

    # Verify backend is reachable
    try:
        api_client._request("GET", "/health")
    except Exception:
        console.print("[red bold]Cannot reach backend at {}. Is it running?[/red bold]".format(args.backend_url))
        sys.exit(1)

    # Set up tool registry
    ToolRegistry.set_api_client(api_client)

    # Set up memory
    memory = CustomerMemory(api_client)

    # Identify customer
    customer_context = identify_customer(memory)

    # Create LLM client
    llm_kwargs: dict = {"model_name": args.model}
    if args.provider == "gemini":
        llm_kwargs["api_key"] = Config.GOOGLE_API_KEY
    elif args.provider == "openai":
        llm_kwargs["api_key"] = Config.OPENAI_API_KEY
        llm_kwargs["base_url"] = Config.OPENAI_BASE_URL
    elif args.provider == "ollama":
        llm_kwargs["api_key"] = "ollama"
        llm_kwargs["base_url"] = "http://localhost:11434/v1"

    try:
        llm_client = create_llm_client(provider=args.provider, **llm_kwargs)
    except Exception as e:
        console.print(f"[red bold]Failed to create LLM client: {e}[/red bold]")
        sys.exit(1)

    # Create agent loop
    agent = AgentLoop(
        llm_client=llm_client,
        customer_context=customer_context,
        verbose=args.verbose,
        max_iterations=Config.MAX_ITERATIONS,
    )

    console.print(
        Panel(
            "[bold]Ready! Type your message below.[/bold]\n"
            "[dim]Type 'quit' or 'exit' to end the session.[/dim]",
            style="blue",
        )
    )

    # Conversation loop
    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            console.print("\n[dim]Thank you for visiting The Golden Plate! See you soon. 👋[/dim]")
            break

        # Process message through agent
        try:
            response = agent.process_message(user_input)
            console.print()
            console.print(Panel(Markdown(response), title="🤖 Agent", border_style="green"))
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            if args.verbose:
                import traceback
                traceback.print_exc()

    api_client.close()


if __name__ == "__main__":
    main()
