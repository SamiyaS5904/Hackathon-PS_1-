#!/usr/bin/env bash
# Assistant in the background (only reachable inside the container), backend in front on the Space's port.
set -e
cd /home/user/app/chatbot
CORS_ORIGINS="" python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 &
cd /home/user/app/backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 7860 --workers 1
