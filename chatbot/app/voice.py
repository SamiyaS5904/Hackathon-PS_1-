"""Cloud voice: speech-to-text and text-to-speech through OpenAI's audio API (plain HTTPS, no extra package).

Optional: without ``OPENAI_API_KEY`` / ``OPENROUTER_API_KEY`` the web app uses the browser's own speech recognition and voices.
Both functions sit behind one small interface so another provider can be swapped in later.
"""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator

import httpx

# OpenAI directly (OPENAI_API_KEY), or the same models through OpenRouter (OPENROUTER_API_KEY), which takes
# the same requests. Model names can be changed with VOICE_STT_MODEL / VOICE_TTS_MODEL / VOICE_TTS_VOICE.
_ROUTER = not os.environ.get("OPENAI_API_KEY") and bool(os.environ.get("OPENROUTER_API_KEY"))
OPENAI_URL = "https://openrouter.ai/api/v1" if _ROUTER else "https://api.openai.com/v1"
STT_MODEL = os.environ.get("VOICE_STT_MODEL", "openai/gpt-4o-transcribe" if _ROUTER else "gpt-4o-transcribe")
TTS_MODEL = os.environ.get("VOICE_TTS_MODEL", "openai/gpt-4o-mini-tts-2025-12-15" if _ROUTER else "gpt-4o-mini-tts")
TTS_VOICE = os.environ.get("VOICE_TTS_VOICE", "coral")
# "en" keeps Hinglish in Roman script ("kal mera lecture kab hai"); without it Hindi-heavy speech comes back in
# Devanagari. Set VOICE_STT_LANGUAGE= (empty) to let the model decide.
STT_LANGUAGE = os.environ.get("VOICE_STT_LANGUAGE", "en")
TTS_STYLE = ("Warm, clear and quick, like a helpful college office colleague. Indian English accent; say Hindi words "
             "in Roman-script Hinglish naturally. Read times like '10:30' as 'ten thirty'.")
MAX_AUDIO = 10 * 1024 * 1024  # ~10 minutes of compressed speech
MAX_TEXT = 1200


class VoiceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    """Shared client (creating one costs ~0.6 s on Windows; reusing it also keeps the connection to OpenAI warm)."""
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=40)
    return _http


def _key() -> str:
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or ""


def available() -> bool:
    return bool(_key())


def _headers() -> dict:
    return {"Authorization": f"Bearer {_key()}"}


def _ext(content_type: str) -> str:
    ct = content_type.split(";")[0].strip().lower()
    return {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3",
            "audio/wav": "wav", "audio/x-wav": "wav"}.get(ct, "webm")


# What speech-to-text models write for silence, breathing or room noise. A whole transcript like this is dropped.
_NOISE = re.compile(
    r"^\W*(thank you( (so|very) much)?( for watching)?|thanks for watching|you|hmm+|uh+|um+|ah+|oh+|"
    r"subtitles by .*|please subscribe.*|\.+|music|\[.*\]|\(.*\))\W*$", re.I)


def clean(text: str) -> str:
    """The transcript, or "" when it is only what the model writes for silence or noise."""
    text = " ".join(text.split())
    return "" if not text or _NOISE.match(text) else text


async def transcribe(audio: bytes, content_type: str) -> str:
    """No prompt is sent: with a quiet recording the model would echo the prompt's words back as if they were said."""
    if not available():
        raise VoiceError(503, "Cloud voice isn't set up.")
    if not audio:
        raise VoiceError(422, "No audio received.")
    if len(audio) > MAX_AUDIO:
        raise VoiceError(413, "That recording is too long. Keep it under a few minutes.")
    files = {"file": (f"speech.{_ext(content_type)}", audio, content_type.split(";")[0] or "audio/webm")}
    data = {"model": STT_MODEL, "response_format": "json",
            **({"language": STT_LANGUAGE} if STT_LANGUAGE else {})}
    try:
        r = await _client().post(f"{OPENAI_URL}/audio/transcriptions", headers=_headers(), files=files, data=data)
    except httpx.HTTPError as exc:
        raise VoiceError(502, "Couldn't reach the voice service.") from exc
    if r.status_code in (401, 403):
        raise VoiceError(503, "The voice key in chatbot/.env isn't accepted (or has no credit left).")
    if r.status_code >= 400:
        raise VoiceError(502, "The voice service couldn't read that. Try again or type it.")
    return clean(r.json().get("text") or "")


async def speech(text: str) -> AsyncIterator[bytes]:
    """MP3 audio of ``text``, streamed as it is made (playback starts sooner)."""
    if not available():
        raise VoiceError(503, "Cloud voice isn't set up.")
    body = {"model": TTS_MODEL, "voice": TTS_VOICE, "input": text[:MAX_TEXT], "instructions": TTS_STYLE,
            "response_format": "mp3"}
    client = _client()
    try:
        req = client.build_request("POST", f"{OPENAI_URL}/audio/speech", headers=_headers(), json=body)
        r = await client.send(req, stream=True)
    except httpx.HTTPError as exc:
        raise VoiceError(502, "Couldn't reach the voice service.") from exc
    if r.status_code >= 400:
        await r.aclose()
        raise VoiceError(503 if r.status_code in (401, 403) else 502, "The voice service didn't answer.")

    async def chunks() -> AsyncIterator[bytes]:
        try:
            async for c in r.aiter_bytes():
                yield c
        finally:
            await r.aclose()

    return chunks()
