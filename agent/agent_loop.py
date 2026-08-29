"""Core agent loop — orchestrates LLM ↔ tool dispatch cycle."""

import json
import logging
from typing import Optional

from agent.config import Config
from agent.llm_client import BaseLLMClient, LLMResponse
from agent.tools.registry import ToolRegistry
from agent.prompts import build_system_prompt

logger = logging.getLogger(__name__)


class AgentLoop:
    """Agentic loop: user message → LLM → (tool calls → results →)* → text reply.

    The loop continues calling tools and feeding results back to the LLM
    until the LLM produces a text response or the iteration limit is hit.
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        customer_context: Optional[dict] = None,
        verbose: bool = False,
        max_iterations: int = 15,
    ):
        self.llm = llm_client
        self.customer_context = customer_context
        self.verbose = verbose
        self.max_iterations = max_iterations

        # Conversation history in OpenAI message format
        self._history: list[dict] = []

        # Build system prompt with customer memory
        self._system_prompt = build_system_prompt(customer_context)

    def set_customer_context(self, context: dict) -> None:
        """Update customer context and rebuild the system prompt."""
        self.customer_context = context
        self._system_prompt = build_system_prompt(context)

    def _build_messages(self) -> list[dict]:
        """Assemble the full message list: system + conversation history."""
        return [{"role": "system", "content": self._system_prompt}] + self._history

    def _log_verbose(self, label: str, data: object) -> None:
        """Print reasoning trace if verbose mode is on."""
        if self.verbose:
            print(f"\n  🔍 [{label}] {json.dumps(data, default=str, indent=2)[:500]}")

    def process_message(self, user_message: str) -> str:
        """Process one user message and return the agent's natural-language response.

        This is the main entry point. It may involve multiple LLM ↔ tool
        round-trips before producing a final text answer.

        Args:
            user_message: The customer's natural-language input.

        Returns:
            The agent's text response.
        """
        # Add user message to history
        self._history.append({"role": "user", "content": user_message})
        self._log_verbose("USER", user_message)

        tool_definitions = ToolRegistry.get_definitions()
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            messages = self._build_messages()

            # Call the LLM
            try:
                response: LLMResponse = self.llm.chat(
                    messages=messages,
                    tools=tool_definitions if tool_definitions else None,
                )
            except Exception as e:
                logger.exception("LLM call failed")
                error_msg = f"I'm sorry, I encountered a technical issue: {e}"
                self._history.append({"role": "assistant", "content": error_msg})
                return error_msg

            # If the LLM returned text (no tool calls) → we're done
            if not response.has_tool_calls:
                text = response.content or ""
                self._history.append({"role": "assistant", "content": text})
                self._log_verbose("RESPONSE", text[:200])
                return text

            # LLM wants to call tools — record the assistant message with tool calls
            assistant_msg: dict = {
                "role": "assistant",
                "content": None,
                "_raw_content": getattr(response, "_raw_content", None),
                "tool_calls": [],
            }
            for tc in response.tool_calls:
                assistant_msg["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, default=str),
                    },
                })
            self._history.append(assistant_msg)

            # Dispatch each tool call and collect results
            for tc in response.tool_calls:
                self._log_verbose("TOOL CALL", {"name": tc.name, "args": tc.arguments})

                result = ToolRegistry.dispatch(tc.name, tc.arguments)
                self._log_verbose("TOOL RESULT", result[:300])

                # Add tool result to history
                self._history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result,
                })

        # Safety: hit max iterations
        fallback = "I've been working on this for a while. Let me summarise what I've done so far. Could you try rephrasing your request?"
        self._history.append({"role": "assistant", "content": fallback})
        return fallback

    def get_history(self) -> list[dict]:
        """Return a copy of the conversation history (for debugging/testing)."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear conversation history (start fresh)."""
        self._history.clear()
