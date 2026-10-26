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
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import language, voice
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


PLATFORM = "platform"  # org value the platform page sends


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
    voice: bool = False  # the message was spoken (speech-to-text) and the reply may be read aloud


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
    spoken = (" Spoken message (speech-to-text): words may be misheard, so match names, sections and subjects to the "
              "closest real ones; the reply is read aloud, so keep it short and avoid long lists.") if req.voice else ""
    return (f"Context: today is {d.strftime('%a %Y-%m-%d')}, time {now}. This week: {week}. Next week: {nxt}."
            f"{on_screen}{spoken} {language.instruction(language.detect(req.message))}.")


_checked: dict[tuple[str, str], float] = {}  # (token, org) -> when the login was last confirmed (voice calls)


async def _member(authorization: str | None, org: str) -> Backend:
    """The caller's backend client, after checking they are logged in and belong to ``org``.
    A confirmed login is trusted for 60 s, so reading an answer aloud sentence by sentence stays quick."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in.")
    token = authorization.split(" ", 1)[1]
    backend = Backend(token, org)
    if time.time() - _checked.get((token, org), 0) < 60:
        return backend
    try:
        me = await backend.me()
    except BackendError as exc:
        await backend.close()
        raise HTTPException(401 if exc.status == 401 else 502, exc.message) from exc
    if org != PLATFORM and not any(m["org_id"] == org for m in me["memberships"]):
        await backend.close()
        raise HTTPException(404, "College not found.")
    if len(_checked) > 5000:
        _checked.clear()
    _checked[(token, org)] = time.time()
    return backend


@app.get("/voice")
def voice_info() -> dict:
    """Whether cloud listening and speaking are set up (otherwise the browser's own voice is used)."""
    return {"cloud": voice.available()}


@app.post("/transcribe")
async def transcribe(request: Request, org: str, authorization: str | None = Header(default=None)) -> dict:
    """Speech-to-text for the chat panel. Body: the recorded audio (webm / ogg / mp4)."""
    backend = await _member(authorization, org)
    try:
        names: list[str] = []
        if org != PLATFORM:
            try:
                c = await backend.college()
                names = [s["name"] for s in c["sections"]] + [t["name"] for t in c["teachers"]]                     + [s["name"] for s in c["subjects"]]
            except BackendError:
                names = []
        audio = await request.body()
        text = await voice.transcribe(audio, request.headers.get("content-type", "audio/webm"), names)
    except voice.VoiceError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    finally:
        await backend.close()
    return {"text": text}


class SpeakRequest(BaseModel):
    org: str
    text: str


@app.post("/speak")
async def speak(req: SpeakRequest, authorization: str | None = Header(default=None)) -> StreamingResponse:
    """Text-to-speech (MP3, streamed) for reading answers aloud."""
    backend = await _member(authorization, req.org)
    await backend.close()
    if not req.text.strip():
        raise HTTPException(422, "Nothing to read.")
    try:
        audio = await voice.speech(req.text.strip())
    except voice.VoiceError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return StreamingResponse(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


# Text waiting to be spoken: POST /speak/start keeps it under a random id for a minute, and the browser's audio
# player fetches GET /speak/{id} and plays it while it is still arriving (no login token in the link).
_to_speak: dict[str, tuple[float, str]] = {}


@app.post("/speak/start")
async def speak_start(req: SpeakRequest, authorization: str | None = Header(default=None)) -> dict:
    backend = await _member(authorization, req.org)
    await backend.close()
    if not voice.available():
        raise HTTPException(503, "Cloud voice isn't set up.")
    if not req.text.strip():
        raise HTTPException(422, "Nothing to read.")
    now = time.time()
    for k in [k for k, (at, _) in _to_speak.items() if now - at > 60]:
        _to_speak.pop(k, None)
    sid = uuid.uuid4().hex
    _to_speak[sid] = (now, req.text.strip()[: voice.MAX_TEXT])
    return {"id": sid}


@app.get("/speak/{sid}")
async def speak_stream(sid: str) -> StreamingResponse:
    item = _to_speak.pop(sid, None)  # one use
    if item is None or time.time() - item[0] > 60:
        raise HTTPException(404, "Nothing to read.")
    try:
        audio = await voice.speech(item[1])
    except voice.VoiceError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return StreamingResponse(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


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
    if req.org == PLATFORM:  # the platform owner's assistant: every college, never college data
        member = {"role": "platform", "name": me["name"], "teacher_id": None} if me.get("platform_owner") else None
    else:
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
            name = "the Timetabl.ai platform" if req.org == PLATFORM else (await ctx.college())["name"]
            async for ev in run_turn(get_client(), conv, ctx, name, req.message.strip(),
                                     _context_line(req, today, now)):
                yield _sse(ev)
        except BackendError as exc:
            yield _sse({"type": "error", "message": exc.message})
            yield _sse({"type": "done"})
        finally:
            if ctx.usage and req.org != PLATFORM:  # the College Admin's cost card
                try:
                    await backend.record_usage(ctx.usage)
                except Exception:  # noqa: BLE001 - the answer matters more than the bookkeeping
                    pass
            await backend.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
