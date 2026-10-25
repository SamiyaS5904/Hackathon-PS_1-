"""Thin client for the Timetabl.ai backend. Every call carries the end user's own token,
so the backend's permission rules apply to the assistant exactly as to the user."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import BACKEND_URL


class BackendError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Backend:
    def __init__(self, token: str, org: str, transport: httpx.AsyncBaseTransport | None = None):
        self.org = org
        self._client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0, transport=transport,
                                         headers={"Authorization": f"Bearer {token}"})

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, **kw: Any) -> Any:
        try:
            r = await self._client.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise BackendError(0, "The timetable server isn't reachable right now.") from exc
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except ValueError:
                detail = None
            raise BackendError(r.status_code, detail if isinstance(detail, str) else f"Request failed ({r.status_code})")
        return r.json() if r.content else None

    def _o(self, path: str) -> str:
        return f"/api/orgs/{self.org}{path}"

    # ---- reads ----
    async def me(self) -> dict:
        return await self._call("GET", "/api/me")

    async def college(self) -> dict:
        return await self._call("GET", self._o("/college"))

    async def timetable(self) -> dict:
        return await self._call("GET", self._o("/timetable"))

    async def week(self, start: str) -> dict:
        return await self._call("GET", self._o("/timetable/week"), params={"start": start})

    async def free_rooms(self, date: str | None, at: str | None, min_seats: int = 0) -> list:
        params = {k: v for k, v in {"date": date, "at": at, "min_seats": min_seats}.items() if v}
        return await self._call("GET", self._o("/free-rooms"), params=params)

    async def teacher_now(self, teacher_id: str, date: str | None, at: str | None) -> dict:
        params = {k: v for k, v in {"date": date, "at": at}.items() if v}
        return await self._call("GET", self._o(f"/teachers/{teacher_id}/now"), params=params)

    async def explain(self, session_id: str) -> dict:
        return await self._call("GET", self._o(f"/timetable/sessions/{session_id}/explain"))

    async def move_options(self, session_id: str) -> list:
        return await self._call("GET", self._o(f"/timetable/sessions/{session_id}/options"))

    async def day_options(self, session_id: str, date: str, to_date: str) -> list:
        return await self._call("GET", self._o(f"/timetable/sessions/{session_id}/day-options"),
                                params={"date": date, "to_date": to_date})

    async def makeup(self, session_id: str, date: str) -> list:
        return await self._call("GET", self._o(f"/timetable/sessions/{session_id}/makeup"),
                                params={"date": date, "days": 7})

    async def my_attendance(self) -> dict:
        return await self._call("GET", self._o("/attendance/me"))

    async def my_classes(self) -> list:
        return await self._call("GET", self._o("/attendance/my-classes"))

    async def section_attendance(self, section_id: str) -> dict:
        return await self._call("GET", self._o(f"/attendance/sections/{section_id}"))

    async def readiness(self) -> list:
        return await self._call("GET", self._o("/readiness"))

    async def insights(self) -> list:
        return await self._call("GET", self._o("/insights"))

    # ---- proposals (never applied here: the user applies them in the app) ----
    async def propose(self, session_id: str, day: str, start_period: int) -> dict:
        return await self._call("POST", self._o("/proposals"),
                                json={"session_id": session_id, "day": day, "start_period": start_period,
                                      "via": "chatbot"})
