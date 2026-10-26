"""One public address for a single-container deployment (e.g. a Hugging Face Space): requests to
/assistant/... are passed to the assistant service running next to the backend (ASSISTANT_URL), streams included
(chat answers, spoken audio). Off unless ASSISTANT_URL is set; the assistant still checks every login itself."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

ASSISTANT_URL = os.environ.get("ASSISTANT_URL", "").rstrip("/")
# Not passed on: connection details, and Origin (CORS is answered here, once, by the backend).
_SKIP = {"host", "content-length", "connection", "origin", "referer", "accept-encoding"}
_KEEP = {"content-type", "cache-control", "x-accel-buffering"}

router = APIRouter(tags=["assistant"])
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, read=300.0))
    return _client


@router.api_route("/assistant/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def to_assistant(path: str, request: Request) -> StreamingResponse:
    if not ASSISTANT_URL:
        raise HTTPException(404, "Not found")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _SKIP}
    req = _http().build_request(request.method, f"{ASSISTANT_URL}/{path}", params=request.query_params,
                                headers=headers, content=await request.body())
    try:
        r = await _http().send(req, stream=True)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "The assistant isn't reachable right now.") from exc
    return StreamingResponse(r.aiter_raw(), status_code=r.status_code,
                             headers={k: v for k, v in r.headers.items() if k.lower() in _KEEP},
                             background=BackgroundTask(r.aclose))
