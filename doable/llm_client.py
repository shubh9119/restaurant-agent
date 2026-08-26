"""LLM client — Gemini with thought-signature preservation."""
import json
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    _raw_content: object = None  # Preserves Gemini thought_signatures

    @property
    def has_tool_calls(self):
        return len(self.tool_calls) > 0


class GeminiClient:
    def __init__(self, api_key, model="gemini-3.6-flash"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def chat(self, messages, tools=None):
        from google.genai import types

        system_text = ""
        contents = []

        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_text = msg["content"]
            elif role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg["content"])]))
            elif role == "assistant":
                # Use raw content if available (preserves thought_signatures)
                if msg.get("_raw_content") is not None:
                    contents.append(msg["_raw_content"])
                elif msg.get("content"):
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg["content"])]))
            elif role == "tool":
                result = msg["content"]
                if isinstance(result, str):
                    try: result = json.loads(result)
                    except: result = {"raw": result}
                contents.append(types.Content(role="user", parts=[
                    types.Part.from_function_response(name=msg.get("name", "unknown"), response=result)
                ]))

        # Build tool declarations
        gemini_tools = None
        if tools:
            decls = [types.FunctionDeclaration(
                name=t["function"]["name"],
                description=t["function"]["description"],
                parameters=t["function"].get("parameters", {})
            ) for t in tools]
            gemini_tools = [types.Tool(function_declarations=decls)]

        config = types.GenerateContentConfig(
            system_instruction=system_text or None,
            tools=gemini_tools,
        )
        response = self.client.models.generate_content(
            model=self.model, contents=contents, config=config
        )

        if not response.candidates:
            return LLMResponse(content="Sorry, I couldn't generate a response.")

        raw_content = response.candidates[0].content
        tool_calls, text_parts = [], []

        for part in raw_content.parts:
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
            return LLMResponse(tool_calls=tool_calls, _raw_content=raw_content)
        return LLMResponse(content="\n".join(text_parts), _raw_content=raw_content)
