"""Timetabl.ai assistant service.

POST /chat streams Server-Sent Events. The caller's own login token is forwarded to the
backend for every lookup, so the assistant can never see or do more than the user.
"""

from __future__ import annotations

import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta

import anthropic
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import Conversation, run_turn
from app.backend import Backend, BackendError
from app.config import CORS_ORIGINS, MAX_HISTORY_MESSAGES, has_api_key
from app.tools import ToolContext

_conversations: dict[str, Conversation] = {}
_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if _client is not None:
        await _client.close()


app = FastAPI(title="Timetabl.ai assistant", version="0.6.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class PageContext(BaseModel):
    path: str = ""
    view: str | None = None  # section | teacher | venue
    entity: str | None = None  # name of what's on screen, e.g. "CSE-3A"
    mode: str | None = None  # plan | week


class ChatRequest(BaseModel):
    org: str
    message: str
    conversation_id: str | None = None
    page: PageContext = PageContext()
    today: str | None = None  # the user's local date (YYYY-MM-DD) and time (HH:MM)
    now: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "assistant_configured": has_api_key()}


def _context_line(req: ChatRequest, today: str, now: str) -> str:
    d = date.fromisoformat(today)
    monday = d - timedelta(days=d.weekday())
    week = ", ".join((monday + timedelta(days=i)).strftime("%a %Y-%m-%d") for i in range(7))
    nxt = ", ".join((monday + timedelta(days=7 + i)).strftime("%a %Y-%m-%d") for i in range(7))
    on_screen = ""
    if req.page.entity:
        on_screen = f" On screen: {req.page.view or ''} {req.page.entity} ({req.page.mode or 'plan'} view)."
    return f"Context: today is {d.strftime('%a %Y-%m-%d')}, time {now}. This week: {week}. Next week: {nxt}.{on_screen}"


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(req: ChatRequest, authorization: str | None = Header(default=None)) -> StreamingResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in.")
    if not req.message.strip():
        raise HTTPException(422, "Type a question.")
    if len(req.message) > 2000:
        raise HTTPException(422, "That message is too long (2000 characters max).")
    token = authorization.split(" ", 1)[1]
    backend = Backend(token, req.org)
    try:
        me = await backend.me()
    except BackendError as exc:
        await backend.close()
        raise HTTPException(401 if exc.status == 401 else 502, exc.message) from exc
    member = next((m for m in me["memberships"] if m["org_id"] == req.org), None)
    if member is None:
        await backend.close()
        raise HTTPException(404, "College not found.")

    conv_id = req.conversation_id or uuid.uuid4().hex
    conv = _conversations.get(conv_id)
    if conv is None or conv.owner != me["user_id"] or conv.org != req.org or len(conv.messages) > MAX_HISTORY_MESSAGES:
        conv_id = uuid.uuid4().hex  # never reuse an id the caller sent that isn't theirs
        conv = Conversation(owner=me["user_id"], org=req.org)
        _conversations[conv_id] = conv

    today = req.today or time.strftime("%Y-%m-%d")
    now = req.now or time.strftime("%H:%M")
    ctx = ToolContext(backend=backend, member=member, today=today, now=now)

    async def events():
        yield _sse({"type": "start", "conversation_id": conv_id})
        try:
            if not has_api_key():
                yield _sse({"type": "error", "message": "The assistant isn't set up yet: add ANTHROPIC_API_KEY to "
                                                        "chatbot/.env and restart the assistant service."})
                yield _sse({"type": "done"})
                return
            college = await ctx.college()
            async for ev in run_turn(get_client(), conv, ctx, college["name"], req.message.strip(),
                                     _context_line(req, today, now)):
                yield _sse(ev)
        except BackendError as exc:
            yield _sse({"type": "error", "message": exc.message})
            yield _sse({"type": "done"})
        finally:
            await backend.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
