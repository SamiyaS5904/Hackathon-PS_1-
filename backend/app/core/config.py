"""Settings from environment variables (and backend/.env if present). Never hard-code secrets."""

from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# Empty DATABASE_URL -> local SQLite file (development / offline demo).
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(ROOT / 'timetabl.db').as_posix()}"
if DATABASE_URL.startswith("postgres://"):  # Supabase sometimes shows this scheme
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

APP_SECRET = os.environ.get("APP_SECRET") or ""
if not APP_SECRET:
    APP_SECRET = secrets.token_urlsafe(32)
    warnings.warn("APP_SECRET is not set: using a random one, so logins reset when the server restarts.",
                  stacklevel=1)

TOKEN_DAYS = int(os.environ.get("TOKEN_DAYS", "7"))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", FRONTEND_URL).split(",") if o.strip()]
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")
# Build and publish the demo college's timetable at startup when it is missing or out of date.
AUTO_DEMO_TIMETABLE = os.environ.get("AUTO_DEMO_TIMETABLE", "1") == "1"
# Platform owners (Super Admin): see every college's health and manage plans / pauses, never college data.
SUPERADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("SUPERADMIN_EMAILS", "").split(",") if e.strip()}
# A demo platform owner (owner@demo.timetabl.ai, DEMO_PASSWORD) for showing the SaaS view; set 0 in production.
DEMO_PLATFORM_OWNER = os.environ.get("DEMO_PLATFORM_OWNER", "1") == "1"
