"""Chatbot settings from environment variables (and chatbot/.env). The API key lives only here."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # chatbot/


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# "localhost" on Windows tries IPv6 first and waits ~0.2 s per connection before falling back; the assistant
# makes several backend calls per answer, so talk to the same machine by its IPv4 address directly.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/").replace("://localhost", "://127.0.0.1")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

MODEL = os.environ.get("CHAT_MODEL", "claude-opus-5-5")
# Chat answers and small tool loops: Claude Opus 5.5 defaults to "medium"; set it explicitly.
EFFORT = os.environ.get("CHAT_EFFORT", "medium")
MAX_TOKENS = 16000
MAX_TOOL_STEPS = 8  # tool rounds per user message
MAX_HISTORY_MESSAGES = 60  # start a fresh conversation beyond this


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
