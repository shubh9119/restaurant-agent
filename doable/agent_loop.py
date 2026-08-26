"""Agent loop — LLM <-> tool dispatch cycle with customer memory."""
import json
from datetime import datetime
from tools import get_tool_definitions, dispatch


def build_system_prompt(customer_context=None):
    now = datetime.now()
    prompt = f"""You are the friendly AI receptionist for "The Golden Plate" restaurant.
Today is {now.strftime("%A")}, {now.strftime("%Y-%m-%d")}. Current time is {now.strftime("%H:%M")}.

Your job:
1. Handle table reservations (check availability first, pick smallest fitting table).
2. Answer menu questions (dietary tags, prices, availability).
3. Manage food orders attached to existing reservations.
4. Remember and respect customer preferences and allergies.

Rules:
- Valid time slots: 30-min increments from 12:00 to 22:30.
- Cannot cancel within 2 hours of slot time.
- Always confirm reservation ID after booking.
- If multiple steps needed (check availability -> book -> order), do them in sequence.
"""
    if customer_context:
        prompt += "\n--- CUSTOMER MEMORY ---\n"
        if customer_context.get("name"):
            prompt += f"Name: {customer_context['name']}\n"
        if customer_context.get("id"):
            prompt += f"Customer ID: {customer_context['id']}\n"
        prefs = customer_context.get("preferences", {})
        if prefs.get("seating_preference"):
            prompt += f"Seating: {prefs['seating_preference']}\n"
        if prefs.get("dietary_restrictions"):
            r = prefs["dietary_restrictions"]
            prompt += f"Dietary: {', '.join(r) if isinstance(r, list) else r}\n"
        if prefs.get("favorite_dishes"):
            d = prefs["favorite_dishes"]
            prompt += f"Favorites: {', '.join(d) if isinstance(d, list) else d}\n"
        if customer_context.get("recent_orders"):
            prompt += f"Recent Orders: {customer_context['recent_orders']}\n"
        prompt += "Use this memory to personalize responses.\n"
    return prompt


class Agent:
    def __init__(self, llm_client, customer_context=None, verbose=False, max_iterations=10):
        self.llm = llm_client
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.history = []
        self.system_prompt = build_system_prompt(customer_context)

    def process_message(self, user_text):
        """Process one user message. Returns agent's text reply. Never crashes."""
        self.history.append({"role": "user", "content": user_text})
        tools = get_tool_definitions()

        for iteration in range(1, self.max_iterations + 1):
            messages = [{"role": "system", "content": self.system_prompt}] + self.history

            if self.verbose:
                print(f"\n[Agent Step {iteration}] Calling LLM...")

            try:
                response = self.llm.chat(messages, tools=tools)
            except Exception as e:
                error_msg = f"I apologize, I encountered a technical issue: {e}"
                if self.verbose:
                    print(f" !! [LLM Error] {e}")
                self.history.append({"role": "assistant", "content": error_msg})
                return error_msg

            # Text response — done
            if not response.has_tool_calls:
                reply = response.content or ""
                self.history.append({"role": "assistant", "content": reply})
                return reply

            # Tool calls — record assistant message with raw content
            self.history.append({
                "role": "assistant", "content": None,
                "_raw_content": getattr(response, '_raw_content', None),
                "tool_calls": [{
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                } for tc in response.tool_calls],
            })

            # Execute each tool
            for tc in response.tool_calls:
                if self.verbose:
                    print(f" -> [Tool Call] {tc.name}({tc.arguments})")
                try:
                    result = dispatch(tc.name, tc.arguments)
                except Exception as e:
                    result = json.dumps({"error": str(e)})
                if self.verbose:
                    print(f" <- [Tool Result] {result[:200]}...")
                self.history.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "name": tc.name, "content": result,
                })

        fallback = "I couldn't complete your request. Could you please rephrase?"
        self.history.append({"role": "assistant", "content": fallback})
        return fallback
