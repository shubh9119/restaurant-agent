"""
FILE 4: agent_loop.py — Core Agent Reasoning & Tool Dispatch Loop.
Write this FOURTH (15 min).

WHY THIS DESIGN:
- Implements the ReAct / Tool-Use cycle:
    1. User sends message -> append to history
    2. Loop:
       a. Send messages + tool definitions to LLM
       b. If LLM returns text only -> reply to user & break
       c. If LLM returns tool calls -> execute each via dispatch()
          and append results to history
       d. Repeat until text reply or max iterations hit
- Separates durable memory (backend) from conversational context (session history)
- Injects customer preferences and recent order history directly into the system prompt.
"""

import json
from datetime import datetime
from tools import get_tool_definitions, dispatch


def build_system_prompt(customer_context: dict = None) -> str:
    """Builds the system prompt with date/time and customer context."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    day_name = now.strftime("%A")

    prompt = f"""You are the friendly AI receptionist for "The Golden Plate" restaurant.
Today is {day_name}, {today_str}. Current time is {current_time}.

Your job:
1. Handle table reservations (check availability first, never exceed capacity).
2. Answer menu questions (dietary tags, prices, availability).
3. Manage food orders attached to existing reservations.
4. Remember and respect customer preferences and allergies.

Business Rules:
- Valid reservation time slots: 30-min increments from 12:00 to 22:30.
- Reservations cannot be cancelled within 2 hours of the slot.
- Orders can only be added or removed before the reservation time has passed.
- If a customer has dietary restrictions or favorite dishes, factor them into recommendations.
- When assigning tables without a specific request, pick the smallest available table that fits the party.
- If multiple steps are required (e.g. check availability -> book table -> add order), perform them in sequence.
- Always provide the reservation ID when a booking is confirmed.
"""
    if customer_context:
        prompt += "\n--- CUSTOMER PROFILE (MEMORY) ---\n"
        if customer_context.get("name"):
            prompt += f"Name: {customer_context['name']}\n"
        if customer_context.get("id"):
            prompt += f"Customer ID: {customer_context['id']}\n"
        prefs = customer_context.get("preferences", {})
        if prefs:
            if prefs.get("seating_preference"):
                prompt += f"Seating Preference: {prefs['seating_preference']}\n"
            if prefs.get("dietary_restrictions"):
                prompt += f"Dietary Restrictions: {', '.join(prefs['dietary_restrictions']) if isinstance(prefs['dietary_restrictions'], list) else prefs['dietary_restrictions']}\n"
            if prefs.get("favorite_dishes"):
                prompt += f"Favorite Dishes: {', '.join(prefs['favorite_dishes']) if isinstance(prefs['favorite_dishes'], list) else prefs['favorite_dishes']}\n"
        if customer_context.get("recent_orders"):
            prompt += f"Recent Orders: {customer_context['recent_orders']}\n"
        prompt += "--- END PROFILE ---\n"
        prompt += "Use this memory naturally to personalize responses without reciting it all at once."

    return prompt


class Agent:
    """Multi-turn agent loop with tool dispatching."""

    def __init__(self, llm_client, customer_context: dict = None, verbose: bool = False, max_iterations: int = 10):
        self.llm = llm_client
        self.customer_context = customer_context
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.history = []
        self.system_prompt = build_system_prompt(customer_context)

    def set_customer_context(self, context: dict):
        self.customer_context = context
        self.system_prompt = build_system_prompt(context)

    def process_message(self, user_text: str) -> str:
        """Process one turn of customer conversation."""
        self.history.append({"role": "user", "content": user_text})

        iteration = 0
        tools = get_tool_definitions()

        while iteration < self.max_iterations:
            iteration += 1
            messages = [{"role": "system", "content": self.system_prompt}] + self.history

            if self.verbose:
                print(f"\n[Agent Step {iteration}] Calling LLM...")

            response = self.llm.chat(messages, tools=tools)

            # If LLM responded with final text (no tool calls), we are done
            if not response.has_tool_calls:
                reply = response.content or ""
                self.history.append({"role": "assistant", "content": reply})
                return reply

            # Record assistant's intent to call tools in history
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            self.history.append(assistant_msg)

            # Execute every tool call and append tool output
            for tc in response.tool_calls:
                if self.verbose:
                    print(f" -> [Tool Call] {tc.name}({tc.arguments})")

                result_json = dispatch(tc.name, tc.arguments)

                if self.verbose:
                    print(f" <- [Tool Result] {result_json[:200]}...")

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result_json,
                })

        fallback = "I apologize, but I couldn't complete your request in time. Could you please rephrase?"
        self.history.append({"role": "assistant", "content": fallback})
        return fallback
