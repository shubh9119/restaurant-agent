"""Tool registry — decorator-based registration with auto JSON schema generation."""

import inspect
import json
import logging
from typing import Any, Callable, Optional, get_type_hints

logger = logging.getLogger(__name__)

# Python type → JSON Schema type mapping
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json_schema(py_type: type) -> dict:
    """Convert a Python type hint to a JSON Schema fragment."""
    origin = getattr(py_type, "__origin__", None)
    if origin is list:
        args = getattr(py_type, "__args__", ())
        item_schema = _python_type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": item_schema}
    if origin is dict:
        return {"type": "object"}
    # Handle Optional[X] which is Union[X, None]
    if origin is type(None):
        return {"type": "string"}
    args = getattr(py_type, "__args__", None)
    if args and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_json_schema(non_none[0])
    return {"type": _TYPE_MAP.get(py_type, "string")}


def _parse_docstring_params(docstring: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style docstring Args section."""
    param_docs: dict[str, str] = {}
    if not docstring:
        return param_docs
    lines = docstring.strip().split("\n")
    in_args = False
    current_param: str | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if in_args:
            if stripped.lower().startswith(("returns:", "raises:", "yields:")):
                break
            # New parameter line: "param_name: description"
            if ":" in stripped and not stripped.startswith(" "):
                parts = stripped.split(":", 1)
                param_name = parts[0].strip()
                param_desc = parts[1].strip() if len(parts) > 1 else ""
                param_docs[param_name] = param_desc
                current_param = param_name
            elif current_param and stripped:
                param_docs[current_param] += " " + stripped
    return param_docs


class ToolRegistry:
    """Central registry for agent tools with safe dispatch."""

    _tools: dict[str, dict[str, Any]] = {}
    _api_client: Any = None

    @classmethod
    def set_api_client(cls, client: Any) -> None:
        """Inject the API client for tools to use."""
        cls._api_client = client

    @classmethod
    def get_api_client(cls) -> Any:
        """Get the injected API client."""
        if cls._api_client is None:
            raise RuntimeError("API client not set. Call ToolRegistry.set_api_client() first.")
        return cls._api_client

    @classmethod
    def reset(cls) -> None:
        """Clear all registered tools and the API client (useful for testing)."""
        cls._tools.clear()
        cls._api_client = None

    @classmethod
    def get_definitions(cls) -> list[dict]:
        """Return tool definitions in OpenAI function-calling format."""
        return [t["definition"] for t in cls._tools.values()]

    @classmethod
    def list_tools(cls) -> list[str]:
        """List registered tool names."""
        return list(cls._tools.keys())

    @classmethod
    def dispatch(cls, tool_name: str, arguments: dict | str) -> str:
        """Execute a tool by name. Returns a JSON string.

        Handles:
        - Unknown tool names → error JSON
        - Malformed arguments (string instead of dict) → attempts JSON parse
        - Execution errors → error JSON
        """
        # Unknown tool guard
        if tool_name not in cls._tools:
            return json.dumps({
                "error": f"Unknown tool '{tool_name}'. Available: {cls.list_tools()}"
            })

        # Parse string arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return json.dumps({
                    "error": f"Malformed arguments for '{tool_name}': could not parse JSON"
                })

        if not isinstance(arguments, dict):
            arguments = {}

        tool_entry = cls._tools[tool_name]
        func = tool_entry["function"]

        try:
            result = func(**arguments)
            return json.dumps(result, default=str)
        except TypeError as e:
            return json.dumps({"error": f"Invalid arguments for '{tool_name}': {e}"})
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' raised an exception")
            return json.dumps({"error": f"Tool '{tool_name}' failed: {e}"})


def tool(description: str = ""):
    """Decorator to register a function as an agent tool.

    Usage::

        @tool("Search the restaurant menu")
        def search_menu(category: str = "", max_price: float = 0) -> dict:
            '''Search menu items.

            Args:
                category: Filter by category.
                max_price: Maximum price filter.
            '''
            ...
    """

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        hints = get_type_hints(func)
        param_docs = _parse_docstring_params(func.__doc__ or "")

        # Build JSON Schema for parameters
        properties: dict[str, dict] = {}
        required: list[str] = []

        for name, param in sig.parameters.items():
            py_type = hints.get(name, str)
            prop = _python_type_to_json_schema(py_type)
            if name in param_docs:
                prop["description"] = param_docs[name]
            properties[name] = prop

            if param.default is inspect.Parameter.empty:
                required.append(name)

        # Description from decorator arg, or first line of docstring
        desc = description
        if not desc and func.__doc__:
            desc = func.__doc__.strip().split("\n")[0]

        tool_def: dict = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

        ToolRegistry._tools[func.__name__] = {
            "function": func,
            "definition": tool_def,
        }

        logger.debug("Registered tool: %s", func.__name__)
        return func

    return decorator
