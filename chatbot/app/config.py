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

# Agentic work (moves, leave cover, makeups, meetings, explanations): fast and accurate. Measured on the demo
# college 2026-10-27: Sonnet 5.5 as accurate as Opus 5.5 on these, ~1.7x faster, half the price.
MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-5-5")
# Used once when the chosen model fails with an API error (overloaded, network), so the answer still comes.
RETRY_MODEL = os.environ.get("CHAT_RETRY_MODEL", "claude-opus-5-5")
# Thinking effort for MODEL / RETRY_MODEL (the fast model uses its own defaults).
EFFORT = os.environ.get("CHAT_EFFORT", "medium")
# Router: simple look-ups ("my next class", "free rooms", "show CSE-3A") go to a fast, much cheaper model;
# anything that changes the timetable, plans or explains goes to MODEL. Empty CHAT_FAST_MODEL = MODEL for all.
FAST_MODEL = os.environ.get("CHAT_FAST_MODEL", "claude-haiku-5-5")
# USD per million tokens: input, output, cache write (5 min), cache read. For the cost card.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 5.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
}
MAX_TOKENS = 16000
MAX_TOOL_STEPS = 8  # tool rounds per user message
MAX_HISTORY_MESSAGES = 60  # start a fresh conversation beyond this


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
