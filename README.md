# 🍽️ AI Restaurant Reception Agent

An AI-powered restaurant receptionist that converses with customers in natural language, manages reservations, places orders, and remembers returning customers' preferences.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Interface (main.py)               │
├─────────────────────────────────────────────────────────┤
│                    Agent Loop                            │
│  user msg → LLM → (tool calls → dispatch → results →)* │
│           → text response                                │
├──────────────┬──────────────────┬────────────────────────┤
│  LLM Client  │  Tool Registry   │  Customer Memory       │
│  (Gemini /   │  (@tool decorator│  (preferences via API) │
│   OpenAI /   │   + dispatch)    │                        │
│   Ollama)    │                  │                        │
├──────────────┴──────────────────┴────────────────────────┤
│                 API Client (httpx)                        │
├─────────────────────────────────────────────────────────┤
│              Restaurant Backend (localhost:8000)          │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start the Backend

**Option A** — Real backend (during the coding round):
```bash
cd restaurant-api
docker compose up -d --build
```

**Option B** — Mock backend (for development/practice):
```bash
python -m mock_backend.app
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Edit .env and set your API key:
# GOOGLE_API_KEY=your-key    (for Gemini)
# OPENAI_API_KEY=your-key    (for OpenAI)
```

### 4. Run the Agent
```bash
# With Gemini (default)
python main.py

# With OpenAI
python main.py --provider openai --model gpt-4o-mini

# With Ollama (local)
python main.py --provider ollama --model llama3

# With reasoning trace
python main.py --verbose
```

### 5. Run Tests
```bash
pytest tests/ -v
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Language** | Python 3.11+ | Best LLM SDK ecosystem, matches FastAPI backend |
| **LLM** | Gemini 2.0 Flash (default) | Free tier, excellent function calling, fast |
| **Tool pattern** | Decorator-based registry | Adding a tool = 1 function + `@tool` decorator. Auto-generates JSON schema from type hints. |
| **Memory** | Backend's own `/preferences` API | No extra database needed. Preferences persist across sessions. |
| **HTTP client** | httpx (sync) | Simple, well-tested, matches FastAPI's test client |
| **Testing** | Stub LLM + Mock API | Tests run without any LLM or backend — fast, deterministic |

## Project Structure

```
restaurant-agent/
├── main.py                      # CLI entry point
├── requirements.txt
├── .env.example
│
├── agent/                       # The agent application
│   ├── config.py                # Environment-based configuration
│   ├── api_client.py            # Typed HTTP client for backend
│   ├── llm_client.py            # LLM abstraction (Gemini/OpenAI/Ollama)
│   ├── agent_loop.py            # Core agentic loop (LLM ↔ tools)
│   ├── memory.py                # Customer memory manager
│   ├── prompts.py               # System prompt templates
│   └── tools/                   # Tool layer
│       ├── registry.py          # @tool decorator + dispatch
│       ├── menu_tools.py        # get_menu, search_menu
│       ├── table_tools.py       # list_tables, check_availability
│       ├── customer_tools.py    # lookup/create/update customer
│       ├── reservation_tools.py # create/get/cancel reservation
│       └── order_tools.py       # add/get/remove order items
│
├── mock_backend/                # Mock API for development
│   ├── app.py                   # FastAPI app (all endpoints)
│   ├── models.py                # Pydantic models
│   └── seed_data.py             # 8 tables, 12 menu items, 3 customers
│
└── tests/                       # Test suite (no real LLM needed)
    ├── conftest.py              # StubLLM, MockAPI, fixtures
    ├── test_tool_registry.py    # Registry mechanics
    ├── test_tools.py            # Each tool unit-tested
    ├── test_agent_loop.py       # End-to-end with stub LLM
    ├── test_memory.py           # Memory load/save
    └── test_error_handling.py   # Error propagation, malformed calls
```

## How It Works

### Agent Loop
1. User sends a message
2. Message is appended to conversation history
3. History + system prompt + tool definitions sent to LLM
4. If LLM returns **tool calls** → dispatch each → add results to history → go to step 3
5. If LLM returns **text** → return to user
6. Safety: max 15 iterations to prevent runaway loops

### Tool System
Tools are plain Python functions decorated with `@tool`:

```python
@tool("Search menu items by category, dietary tags, or maximum price")
def search_menu(category: str = "", dietary_tag: str = "", max_price: float = 0) -> dict:
    """Search and filter menu items.

    Args:
        category: Filter by category.
        dietary_tag: Filter by dietary tag.
        max_price: Maximum price. Use 0 for no limit.
    """
    api = ToolRegistry.get_api_client()
    items = api.get_menu()
    # ... filter logic ...
    return {"results": filtered, "count": len(filtered)}
```

Adding a new tool is a **one-function change**: write the function, add `@tool()`, done.

### Customer Memory
- **Durable state**: Stored in backend via `PATCH /customers/{id}/preferences`
- **Session state**: Conversation history kept in-memory
- **On session start**: Customer identified by phone/email → preferences + order history loaded into system prompt

### Error Handling
- Unknown tools → error JSON returned to LLM
- Malformed arguments → graceful parse with fallback
- Backend HTTP errors → caught by tools, surfaced as natural language
- LLM exceptions → caught by agent loop, user sees friendly message
- Runaway loops → max iteration guard

## Assumptions

1. **Single customer per session**: The CLI identifies one customer at session start
2. **Preference schema is free-form**: We use keys like `seating_preference`, `dietary_restrictions`, `favorite_dishes`, `notes`
3. **Time rounding**: The LLM is instructed to round times to valid 30-minute slots
4. **Smart table assignment**: Available tables are sorted by capacity (smallest first) so the LLM naturally picks the best fit
5. **Menu item lookup by name**: The LLM uses `get_menu` or `search_menu` to find item IDs before placing orders
6. **No authentication**: The backend is accessed without auth tokens (as per the problem statement)

## Example Session

```
Your phone or email: +91-9876543210

Welcome back, Priya Sharma! ✨
  Remembered: Seating: outdoor | Dietary: vegetarian

You: Can I book a table for 3 tonight around 8?

Agent: I see you usually prefer outdoor seating. Let me check availability
       for an outdoor table for 3 tonight at 8:00 PM.
       
       Great news! I've booked Table 7 (outdoor, seats 4) at 20:00 tonight.
       Reservation ID: 3.
       
       Would you like to pre-order? Last time you had Paneer Tikka and
       Dal Makhani.

You: Add one paneer tikka and two dal makhani. And one gulab jamun.

Agent: Added to reservation 3:
       • Paneer Tikka × 1 — ₹350
       • Dal Makhani × 2 — ₹400 each
       • Gulab Jamun × 1 — ₹200
       
       Total: ₹1,350. See you at 8! 🍽️
```
