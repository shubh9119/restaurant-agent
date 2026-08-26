"""Tests for the tool registry — registration, schema, dispatch, errors."""

import json
import pytest
from agent.tools.registry import ToolRegistry, tool


class TestToolRegistration:
    """Test tool decorator and registration mechanics."""

    def test_tool_decorator_registers_function(self):
        """A decorated function should appear in the registry."""
        @tool("A test tool")
        def test_tool_alpha(x: int, y: str = "hello") -> dict:
            """Test tool.

            Args:
                x: An integer.
                y: A string.
            """
            return {"x": x, "y": y}

        assert "test_tool_alpha" in ToolRegistry.list_tools()

    def test_tool_definition_has_correct_schema(self):
        """The generated JSON schema should match the function signature."""
        @tool("Adds two numbers")
        def add_numbers(a: int, b: int) -> dict:
            """Add two numbers.

            Args:
                a: First number.
                b: Second number.
            """
            return {"result": a + b}

        definitions = ToolRegistry.get_definitions()
        add_def = next(d for d in definitions if d["function"]["name"] == "add_numbers")
        params = add_def["function"]["parameters"]

        assert params["type"] == "object"
        assert "a" in params["properties"]
        assert "b" in params["properties"]
        assert params["properties"]["a"]["type"] == "integer"
        assert params["properties"]["b"]["type"] == "integer"
        assert "a" in params["required"]
        assert "b" in params["required"]

    def test_optional_params_not_required(self):
        """Parameters with defaults should not be in 'required'."""
        @tool("Test optional")
        def opt_tool(name: str, limit: int = 10) -> dict:
            """Tool with optional.

            Args:
                name: Required name.
                limit: Optional limit.
            """
            return {}

        definitions = ToolRegistry.get_definitions()
        opt_def = next(d for d in definitions if d["function"]["name"] == "opt_tool")
        required = opt_def["function"]["parameters"]["required"]
        assert "name" in required
        assert "limit" not in required


class TestToolDispatch:
    """Test the dispatch mechanism."""

    def test_dispatch_calls_function(self):
        """Dispatch should call the registered function with correct args."""
        @tool("Echo tool")
        def echo_test(message: str) -> dict:
            """Echo back.

            Args:
                message: Message to echo.
            """
            return {"echo": message}

        result = json.loads(ToolRegistry.dispatch("echo_test", {"message": "hello"}))
        assert result == {"echo": "hello"}

    def test_dispatch_unknown_tool(self):
        """Dispatching an unknown tool should return an error JSON."""
        result = json.loads(ToolRegistry.dispatch("nonexistent_tool_xyz", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_dispatch_malformed_string_args(self):
        """Dispatch should handle malformed JSON string arguments gracefully."""
        @tool("Malformed test tool")
        def malformed_test_tool(msg: str) -> dict:
            """Test.

            Args:
                msg: A message.
            """
            return {"msg": msg}

        result = json.loads(ToolRegistry.dispatch("malformed_test_tool", "not valid json{{{"))
        assert "error" in result
        assert "Malformed" in result["error"]

    def test_dispatch_string_args_parsed(self):
        """Dispatch should parse valid JSON string arguments."""
        @tool("String arg tool")
        def string_arg_tool(value: str) -> dict:
            """Test.

            Args:
                value: A value.
            """
            return {"value": value}

        result = json.loads(ToolRegistry.dispatch("string_arg_tool", '{"value": "test"}'))
        assert result == {"value": "test"}

    def test_dispatch_wrong_args_returns_error(self):
        """Dispatch with wrong argument types should return error."""
        @tool("Typed tool")
        def typed_tool(count: int) -> dict:
            """Test.

            Args:
                count: A count.
            """
            return {"count": count}

        # Missing required arg
        result = json.loads(ToolRegistry.dispatch("typed_tool", {}))
        assert "error" in result

    def test_dispatch_exception_in_tool(self):
        """If a tool raises, dispatch should catch it and return error JSON."""
        @tool("Failing tool")
        def failing_tool() -> dict:
            """This tool always fails."""
            raise ValueError("Something went wrong!")

        result = json.loads(ToolRegistry.dispatch("failing_tool", {}))
        assert "error" in result
        assert "Something went wrong" in result["error"]
