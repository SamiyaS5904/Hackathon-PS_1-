"""Single-container deployment: /assistant/... is passed to the assistant service (streams included)."""

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.routers import assistant_proxy


def test_off_without_assistant_url(monkeypatch):
    monkeypatch.setattr(assistant_proxy, "ASSISTANT_URL", "")
    with TestClient(app) as c:
        assert c.get("/assistant/voice").status_code == 404


def test_requests_are_passed_on_without_origin(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(path=request.url.path, query=dict(request.url.params), auth=request.headers.get("authorization"),
                    origin=request.headers.get("origin"), body=request.content)
        async def stream():  # a real stream, like the assistant's answer
            yield b"data: {}\n\n"

        return httpx.Response(200, headers={"content-type": "text/event-stream", "set-cookie": "x=1"}, content=stream())

    monkeypatch.setattr(assistant_proxy, "ASSISTANT_URL", "http://assistant.local")
    monkeypatch.setattr(assistant_proxy, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with TestClient(app) as c:
        r = c.post("/assistant/transcribe?org=demo", content=b"audio", headers={
            "Authorization": "Bearer t", "Origin": "http://localhost:3000", "Content-Type": "audio/webm"})
    assert r.status_code == 200 and r.text == "data: {}\n\n" and r.headers["content-type"].startswith("text/event-stream")
    assert "set-cookie" not in r.headers
    assert seen == {"path": "/transcribe", "query": {"org": "demo"}, "auth": "Bearer t", "origin": None, "body": b"audio"}
