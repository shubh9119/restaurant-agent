"""
FILE 3: llm_client.py — LLM abstraction (Gemini + OpenAI).
Write this THIRD (15 min).

WHY THIS DESIGN:
- ToolCall and LLMResponse are simple dataclasses — easy to work with
- Each provider is a small class with ONE method: chat()
- chat() takes OpenAI-format messages + tools, returns LLMResponse
- Gemini needs format conversion (OpenAI messages → Gemini contents)
- The agent loop doesn't care which provider is used — same interface

TIP FOR THE ROUND:
- If Gemini gives you trouble, just use OpenAI — fewer conversion steps
- If no API key, use Ollama locally (same code as OpenAI, different base_url)
"""

import json
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """One tool call parsed from the LLM response."""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """LLM response: either text OR tool calls."""
    content: str = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GEMINI CLIENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] = None) -> LLMResponse:
        from google.genai import types

        # Split system message from conversation
        system_text = ""
        contents = []

        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_text = msg["content"]
            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(msg["content"])]))
            elif role == "assistant":
                if msg.get("tool_calls"):
                    parts = []
                    for tc in msg["tool_calls"]:
                        args = tc["function"]["arguments"]
                        if isinstance(args, str):
                            args = json.loads(args)
                        parts.append(types.Part.from_function_call(name=tc["function"]["name"], args=args))
                    contents.append(types.Content(role="model", parts=parts))
                elif msg.get("content"):
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(msg["content"])]))
            elif role == "tool":
                result = msg["content"]
                if isinstance(result, str):
                    try: result = json.loads(result)
                    except: result = {"raw": result}
                contents.append(types.Content(role="user", parts=[
                    types.Part.from_function_response(name=msg.get("name", "unknown"), response=result)
                ]))

        # Convert tool definitions
        gemini_tools = None
        if tools:
            decls = []
            for t in tools:
                f = t["function"]
                decls.append(types.FunctionDeclaration(
                    name=f["name"], description=f["description"], parameters=f.get("parameters", {})
                ))
            gemini_tools = [types.Tool(function_declarations=decls)]

        # Call Gemini
        config = types.GenerateContentConfig(
            system_instruction=system_text or None,
            tools=gemini_tools,
        )
        response = self.client.models.generate_content(model=self.model, contents=contents, config=config)

        # Parse response
        if not response.candidates:
            return LLMResponse(content="Sorry, I couldn't generate a response.")

        tool_calls = []
        text_parts = []
        for part in response.candidates[0].content.parts:
            if part.function_call:
                fc = part.function_call
                tool_calls.append(ToolCall(
                    id=f"call_{fc.name}_{len(tool_calls)}",
                    name=fc.name,
                    arguments=dict(fc.args) if fc.args else {},
                ))
            elif part.text:
                text_parts.append(part.text)

        if tool_calls:
            return LLMResponse(tool_calls=tool_calls)
        return LLMResponse(content="\n".join(text_parts))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OPENAI CLIENT (also works with Ollama)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] = None) -> LLMResponse:
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except: args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
            return LLMResponse(tool_calls=tool_calls)

        return LLMResponse(content=msg.content or "")
