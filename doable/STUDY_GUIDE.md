# 🎯 90-Minute Live Coding Study Guide: AI Restaurant Agent

This guide breaks down the **doable** implementation (~450 lines across 5 core files) that you can comfortably write and explain in a 90-minute live interview.

---

## ⏱️ 90-Minute Live Coding Timeline

```
[00:00 - 00:10] Read backend README & start backend (`docker compose up -d`)
[00:10 - 00:25] File 1: `api_client.py` (Simple HTTP wrapper)
[00:25 - 00:45] File 2: `tools.py` (Tool Registry + Core Tools)  <-- STAR PIECE
[00:45 - 01:00] File 3: `llm_client.py` (Gemini/OpenAI client)
[01:00 - 01:15] File 4: `agent_loop.py` (ReAct Tool loop + Memory prompt)
[01:15 - 01:25] File 5: `main.py` (CLI + Customer identification)
[01:25 - 01:30] File 6: `test_doable.py` (5 key tests with StubLLM)
```

---

## 📂 File-by-File Breakdown & Mental Model

### 1. `api_client.py` (~60 lines)
* **Goal**: A clean, typed Python wrapper around the backend REST API.
* **Why it impresses them**:
  * Centralizes all HTTP calls into `_request(method, path, **kwargs)`.
  * Raises a custom `APIError(status_code, detail)` so tool functions can catch backend errors easily.
  * Every API endpoint is a clean 1-2 line method.

---

### 2. `tools.py` (~120 lines) — ⭐ **Your Star Piece**
* **Goal**: A decorator-based tool registry that automatically turns Python functions into JSON schemas for the LLM.
* **Why it impresses them**:
  * **Auto-Schema Generation**: Uses `inspect.signature` and `typing.get_type_hints` so you **never** have to write manual JSON schemas.
  * **Defensive Dispatch**: `dispatch(name, args)` handles:
    1. Unknown tool names (LLM hallucinations)
    2. Malformed arguments (bad JSON strings)
    3. Tool execution errors / backend exceptions
  * **Extensibility**: Adding a new tool is just writing a function with `@tool("description")`.

---

### 3. `llm_client.py` (~90 lines)
* **Goal**: Abstract LLM interface that handles function calling.
* **Why it impresses them**:
  * `ToolCall` and `LLMResponse` dataclasses normalize responses across different providers.
  * For Gemini: maps OpenAI-style messages (`system`, `user`, `assistant`, `tool`) to Gemini `Content` and `Part` objects.
  * For OpenAI/Ollama: standard `chat.completions.create`.

---

### 4. `agent_loop.py` (~80 lines)
* **Goal**: Multi-turn ReAct reasoning loop.
* **Core Algorithm to Remember**:
  1. Append customer's input to conversation history.
  2. `while iteration < max_iterations`:
     - Send history + system prompt + tool definitions to LLM.
     - **If LLM returns text**: append to history and return response to user.
     - **If LLM returns tool calls**:
       - Record assistant's intent to call tools.
       - Execute each tool via `dispatch()`.
       - Append tool results with role `"tool"` back into history.
       - Repeat the loop so LLM sees tool results and decides next action.
* **Customer Memory**:
  - Injects stored preferences (seating, dietary restrictions, favorites) and recent orders into the system prompt.

---

### 5. `main.py` (~70 lines)
* **Goal**: Interactive CLI with customer identification.
* **Flow**:
  1. Prompts for phone/email.
  2. Calls `api.lookup_customer()` -> if found, loads context and recent orders.
  3. If not found, registers a new customer.
  4. Starts multi-turn chat loop.

---

### 6. `test_doable.py` (~90 lines)
* **Goal**: Unit tests with zero real LLM calls using `StubLLM` and `FakeRestaurantAPI`.
* **Tests**:
  1. `test_tool_registry_and_schema`: Tool schema auto-generation.
  2. `test_tool_dispatch_success`: Successful tool execution.
  3. `test_tool_dispatch_defensive_error_handling`: Hallucinated tools & backend errors.
  4. `test_agent_multi_turn_booking_flow`: Multi-step booking sequence.
  5. `test_customer_memory_in_system_prompt`: Memory injection into system prompt.

---

## 🗣️ What to Say During the Interview

1. **On Architecture**:
   > *"I have cleanly separated the application into 4 decoupled layers: HTTP/Backend client, Tool Registry & Dispatcher, LLM Provider Abstraction, and the Agent Execution Loop."*

2. **On Tool Design**:
   > *"Rather than writing repetitive JSON schemas by hand, I built a lightweight `@tool` decorator that inspects function signatures and type hints. This makes adding any future tool a 1-minute task."*

3. **On Defensive Engineering**:
   > *"The dispatcher defensively catches unknown tool names, stringified JSON arguments, and backend 4xx/5xx exceptions, returning them as structured error messages so the LLM can self-correct instead of crashing the program."*

4. **On Customer Memory**:
   > *"I distinguish durable memory (stored via `PATCH /customers/{id}/preferences` and order history) from conversational state (the session message history). On session start, durable memory is loaded directly into the system prompt to guide recommendations."*

5. **On Testing**:
   > *"The test suite uses a `StubLLM` pattern and an in-memory API fake. This lets us verify complex multi-step booking workflows deterministically in under half a second with zero API costs."*

---

## 🚀 How to Run & Verify

```bash
# 1. Run the test suite
pytest doable/test_doable.py -v

# 2. Run the mock backend (for practice)
python -m mock_backend.app

# 3. In another terminal, run the doable CLI
python doable/main.py --verbose
```
