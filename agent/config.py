"""Centralised configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration sourced from environment / .env file."""

    # Restaurant backend
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # LLM provider selection: "gemini" | "openai" | "ollama"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

    # Model name passed to the provider SDK
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.0-flash")

    # Provider API keys
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Base URL for OpenAI-compatible endpoints (also used for Ollama)
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # Safety: maximum tool-call iterations per user turn
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "15"))

    # Show reasoning trace in output
    VERBOSE: bool = os.getenv("VERBOSE", "false").lower() == "true"
