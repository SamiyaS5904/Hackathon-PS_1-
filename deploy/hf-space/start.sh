#!/usr/bin/env bash
# Assistant in the background (only reachable inside the container), backend in front on the host's port
# ($PORT on Render / Railway, 7860 on a Hugging Face Space).
set -e
PORT="${PORT:-7860}"
export BACKEND_URL="http://127.0.0.1:${PORT}"
cd /home/user/app/chatbot
CORS_ORIGINS="" python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 &
cd /home/user/app/backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1
