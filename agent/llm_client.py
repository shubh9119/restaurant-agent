"""LLM client abstraction — supports Gemini and OpenAI-compatible providers."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A parsed tool/function call from the LLM response."""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Unified LLM response: either text content or tool calls (not both)."""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class BaseLLMClient:
    """Abstract LLM client interface."""

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        """Send messages and tools to the LLM, return a unified response."""
        raise NotImplementedError


class GeminiClient(BaseLLMClient):
    """Google Gemini client using the google-genai SDK."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model_name

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        from google.genai import types

        # Separate system instruction from conversation
        system_text = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")

            if role == "system":
                system_text = msg.get("content", "")

            elif role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg["content"])],
                ))

            elif role == "assistant":
                if msg.get("tool_calls"):
                    # Reconstruct function call parts
                    parts = []
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        parts.append(types.Part.from_function_call(
                            name=func.get("name", ""),
                            args=args,
                        ))
                    contents.append(types.Content(role="model", parts=parts))
                else:
                    text = msg.get("content", "")
                    if text:
                        contents.append(types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=text)],
                        ))

            elif role == "tool":
                # Tool result → FunctionResponse
                result_str = msg.get("content", "{}")
                try:
                    result_dict = json.loads(result_str) if isinstance(result_str, str) else result_str
                except json.JSONDecodeError:
                    result_dict = {"raw": result_str}

                tool_name = msg.get("name", msg.get("tool_call_id", "unknown"))
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=tool_name,
                        response=result_dict,
                    )],
                ))

        # Convert tool definitions to Gemini format
        gemini_tools = None
        if tools:
            declarations = []
            for t in tools:
                func = t.get("function", {})
                params = func.get("parameters", {})
                declarations.append(types.FunctionDeclaration(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=params,
                ))
            gemini_tools = [types.Tool(function_declarations=declarations)]

        # Build config
        config = types.GenerateContentConfig(
            system_instruction=system_text if system_text else None,
            tools=gemini_tools,
        )

        # Call the API
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        # Parse response
        if not response.candidates:
            return LLMResponse(content="I'm sorry, I couldn't generate a response.")

        candidate = response.candidates[0]
        tool_calls = []
        text_parts = []

        for part in candidate.content.parts:
            if part.function_call:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                tool_calls.append(ToolCall(
                    id=f"call_{fc.name}_{len(tool_calls)}",
                    name=fc.name,
                    arguments=args,
                ))
            elif part.text:
                text_parts.append(part.text)

        if tool_calls:
            return LLMResponse(tool_calls=tool_calls)
        return LLMResponse(content="\n".join(text_parts) if text_parts else "")


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible client (works with OpenAI, Ollama, etc.)."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model_name

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
            return LLMResponse(tool_calls=tool_calls)

        return LLMResponse(content=msg.content or "")


def create_llm_client(provider: str, **kwargs: Any) -> BaseLLMClient:
    """Factory to create the right LLM client based on provider name."""
    if provider == "gemini":
        return GeminiClient(
            api_key=kwargs.get("api_key", ""),
            model_name=kwargs.get("model_name", "gemini-2.0-flash"),
        )
    elif provider in ("openai", "ollama"):
        return OpenAIClient(
            api_key=kwargs.get("api_key", "not-needed") if provider == "ollama" else kwargs.get("api_key", ""),
            model_name=kwargs.get("model_name", "gpt-4o-mini"),
            base_url=kwargs.get("base_url", "https://api.openai.com/v1"),
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'gemini', 'openai', or 'ollama'.")
