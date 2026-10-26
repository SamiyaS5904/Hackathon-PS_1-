"""Room booking for events (see app/venue_events.py).

Teachers, Coordinators and the College Admin find free rooms and book them; the Coordinator of the
room's department (College Admin for shared rooms) approves or declines. Students can't book rooms.
Everyone involved is notified. Read against the published timetable when there is one (what really
happens in the rooms).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import venue_events
from app.core.deps import Ctx, allow, org_ctx
from app.models.domain import Timetable
from app.notify import send
from app.venue_events import EventLists, EventOut, FreeVenue

router = APIRouter(prefix="/api/orgs/{org}/venue-events", tags=["venue events"])

TIME = r"^\d{2}:\d{2}$"
DATE = r"^\d{4}-\d{2}-\d{2}$"
LINK = "/events"


def _today_now() -> tuple[str, str]:
    now = time.localtime()
    return time.strftime("%Y-%m-%d", now), time.strftime("%H:%M", now)


def _tt(ctx: Ctx) -> Timetable | None:
    return ctx.state.published or ctx.state.timetable


def _staff_or_teacher(ctx: Ctx) -> None:
    allow("" if ctx.member.role in ("admin", "coordinator", "teacher")
          else "Rooms for events are booked by teachers and staff.")


def _event(ctx: Ctx, event_id: str):
    ev = venue_events.get(ctx.state.id, event_id)
    m = ctx.member
    # Seen by the person who booked it, whoever decides it, and the College Admin; anyone else gets 404.
    if ev is None or not (ev.requested_by == m.user_id or m.role == "admin"
                          or (m.role == "coordinator" and ev.owner_department_id == m.department_id)):
        raise HTTPException(404, "Booking not found.")
    return ev


def _out(ctx: Ctx, ev) -> EventOut:
    today, now = _today_now()
    return venue_events.out(ctx.state.college, _tt(ctx), ctx.state.id, ctx.member, ev, today, now)


@router.get("/free", response_model=list[FreeVenue])
def free(date: str, start: str, end: str, min_seats: int = 0, ctx: Ctx = Depends(org_ctx)) -> list[FreeVenue]:
    _staff_or_teacher(ctx)
    today, now = _today_now()
    rooms, why = venue_events.free_venues(ctx.state.college, _tt(ctx), ctx.state.id, date, start, end, today, now,
                                          max(0, min_seats))
    if why:
        raise HTTPException(422, why)
    return rooms


class EventIn(BaseModel):
    venue_id: str
    date: str = Field(pattern=DATE)
    start: str = Field(pattern=TIME)
    end: str = Field(pattern=TIME)
    title: str = Field(max_length=120)
    club: str = Field(default="", max_length=80)


class EventResult(BaseModel):
    message: str
    event: EventOut


@router.post("", response_model=EventResult, status_code=201)
def book(body: EventIn, ctx: Ctx = Depends(org_ctx)) -> EventResult:
    _staff_or_teacher(ctx)
    today, now = _today_now()
    college = ctx.state.college
    ev, msg = venue_events.request(college, _tt(ctx), ctx.state.id, ctx.member, body.venue_id, body.date, body.start,
                                   body.end, body.title, body.club, today, now)
    if ev is None:
        raise HTTPException(422, msg)
    room = college.venue(ev.venue_id).name
    when = f"{venue_events.label(ev.date)} {ev.start}-{ev.end}"
    what = ev.title + (f" ({ev.club})" if ev.club else "")
    if ev.status == "pending":
        send(ctx.state.id, f"Room request: {room} for {what}", f"{when} · asked by {ctx.member.name}. Approve or "
             "decline it under Room booking.", venue_events.approver_audience(ev), ctx.member.user_id, link=LINK)
    return EventResult(message=msg, event=_out(ctx, ev))


@router.get("", response_model=EventLists)
def lists(ctx: Ctx = Depends(org_ctx)) -> EventLists:
    _staff_or_teacher(ctx)
    today, now = _today_now()
    return venue_events.listing(ctx.state.college, _tt(ctx), ctx.state.id, ctx.member, today, now)


class DecideIn(BaseModel):
    note: str = Field(default="", max_length=300)


def _decide(event_id: str, approve: bool, note: str, ctx: Ctx) -> EventResult:
    ev = _event(ctx, event_id)
    allow(venue_events.can_decide(ctx.member, ev))
    done, msg = venue_events.decide(ctx.state.college, _tt(ctx), ctx.state.id, ctx.member, ev, approve, note)
    if done is None:
        raise HTTPException(409, msg)
    room = ctx.state.college.venue(done.venue_id).name
    when = f"{venue_events.label(done.date)} {done.start}-{done.end}"
    title = (f"Room booked: {room} for {done.title}" if approve
             else f"Room request declined: {room} for {done.title}")
    body = f"{when} · {'approved' if approve else 'declined'} by {ctx.member.name}" + (
        f". Note: {done.note}" if done.note else "")
    send(ctx.state.id, title, body, venue_events.requester_audience(done), ctx.member.user_id, link=LINK)
    return EventResult(message=msg, event=_out(ctx, done))


@router.post("/{event_id}/approve", response_model=EventResult)
def approve(event_id: str, ctx: Ctx = Depends(org_ctx)) -> EventResult:
    return _decide(event_id, True, "", ctx)


@router.post("/{event_id}/decline", response_model=EventResult)
def decline(event_id: str, body: DecideIn, ctx: Ctx = Depends(org_ctx)) -> EventResult:
    return _decide(event_id, False, body.note, ctx)


@router.post("/{event_id}/cancel", response_model=EventResult)
def cancel(event_id: str, ctx: Ctx = Depends(org_ctx)) -> EventResult:
    ev = _event(ctx, event_id)
    done, msg = venue_events.cancel(ctx.state.id, ctx.member, ev)
    if done is None:
        raise HTTPException(409, msg)
    room = ctx.state.college.venue(done.venue_id).name
    when = f"{venue_events.label(done.date)} {done.start}-{done.end}"
    if done.requested_by != ctx.member.user_id:
        send(ctx.state.id, f"Room booking cancelled: {room} for {done.title}", f"{when} · cancelled by "
             f"{ctx.member.name}", venue_events.requester_audience(done), ctx.member.user_id, link=LINK)
    else:  # the approver had it on their list (waiting or held): tell them it's free again
        send(ctx.state.id, f"Room booking cancelled: {room} for {done.title}", f"{when} · cancelled by "
             f"{ctx.member.name}. The room is free again.", venue_events.approver_audience(done), ctx.member.user_id,
             link=LINK)
    return EventResult(message=msg, event=_out(ctx, done))
