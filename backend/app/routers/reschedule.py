"""Reschedule finder for one class (teachers: own lectures; Coordinator: own department; Admin: all).

Read only: the move itself goes through the existing one-day change (POST /overrides) or, for good,
the teacher's change request (POST /change-requests), so every check, log entry and notification
stays in one place.
"""

from __future__ import annotations

import datetime
import time

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import Ctx, allow, org_ctx
from app.permissions import can_edit_one_day
from app.reschedule import RescheduleOut, reschedule_options

router = APIRouter(prefix="/api/orgs/{org}", tags=["reschedule"])


@router.get("/timetable/sessions/{session_id}/reschedule", response_model=RescheduleOut)
def get_reschedule_options(session_id: str, date: str, days: int = 7, ctx: Ctx = Depends(org_ctx)) -> RescheduleOut:
    state = ctx.state
    tt = state.timetable
    if tt is None or not tt.sessions:
        raise HTTPException(404, "No timetable yet.")
    if not ctx.live:
        raise HTTPException(409, "The College Admin is preparing an updated timetable. Changes open again once it "
                                 "is published.")
    if tt.college_revision != state.college.revision:
        raise HTTPException(409, "The college data changed since this timetable was made. Ask the College Admin to "
                                 "update it first.")
    s = next((x for x in tt.sessions if x.id == session_id), None)
    if s is None:
        raise HTTPException(404, "Class not found in the current timetable")
    allow(can_edit_one_day(ctx.member, state.college, s))
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, "Use a date like 2026-10-21") from None
    now = time.localtime()
    return reschedule_options(state.college, tt, session_id, date, time.strftime("%Y-%m-%d", now),
                              time.strftime("%H:%M", now), days=max(1, min(days, 14)))
