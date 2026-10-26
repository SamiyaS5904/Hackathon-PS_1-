"""Cloud voice endpoints: off without a key (the browser's voice is used), login required, Hinglish hint."""

from fastapi.testclient import TestClient

from app import voice
from app.main import app


def test_voice_is_off_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as c:
        assert c.get("/voice").json() == {"cloud": False}
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        assert c.get("/voice").json() == {"cloud": True}


def test_voice_needs_login():
    with TestClient(app) as c:
        assert c.post("/transcribe?org=demo", content=b"abc", headers={"Content-Type": "audio/webm"}).status_code == 401
        assert c.post("/speak", json={"org": "demo", "text": "hi"}).status_code == 401


def test_hint_asks_for_roman_hinglish_and_college_names():
    h = voice._hint(["CSE-3A", "Dr. Anita Sharma"] + [f"Name {i}" for i in range(500)])
    assert "Roman script" in h and "CSE-3A" in h and "Dr. Anita Sharma" in h and len(h) <= 720
    assert voice._ext("audio/webm;codecs=opus") == "webm" and voice._ext("audio/mp4") == "mp4"


def test_spoken_text_ids_are_single_use_and_need_login():
    with TestClient(app) as c:
        assert c.post("/speak/start", json={"org": "demo", "text": "hi"}).status_code == 401
        assert c.get("/speak/not-a-real-id").status_code == 404
