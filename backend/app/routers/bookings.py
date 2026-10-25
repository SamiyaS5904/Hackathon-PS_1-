"""Teacher booking endpoints: office hours, doubt slots (students) and meetings (Coordinator / Admin).

Permissions (root CLAUDE.md §4): a teacher manages their own office hours and sees bookings with them;
a student books and cancels their own doubt slots; a Department Coordinator books meetings with their
own department's teachers; the College Admin with any teacher. Everything is read against the
published timetable when there is one (that is what happens in class).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import bookings
from app.bookings import BookingOut, OfficeHour, Slot
from app.core.deps import Ctx, allow, org_ctx
from app.models.domain import Student, Timetable
from app.notify import Audience, send

router = APIRouter(prefix="/api/orgs/{org}/bookings", tags=["bookings"])

TIME = r"^\d{2}:\d{2}$"
DATE = r"^\d{4}-\d{2}-\d{2}$"


def _today_now() -> tuple[str, str]:
    now = time.localtime()
    return time.strftime("%Y-%m-%d", now), time.strftime("%H:%M", now)


def _tt(ctx: Ctx) -> Timetable | None:
    """What actually happens in class: the published timetable (teachers and students already get it)."""
    return ctx.state.published or ctx.state.timetable


def _student(ctx: Ctx) -> Student:
    if ctx.member.role != "student":
        raise HTTPException(403, "Doubt slots are booked by students.")
    st = next((s for s in ctx.state.college.students if s.email.lower() == ctx.member.email.lower()), None)
    if st is None:
        raise HTTPException(404, "Your name isn't on this college's student list yet.")
    return st


def _teacher_id(ctx: Ctx) -> str:
    if ctx.member.role != "teacher" or not ctx.member.teacher_id:
        raise HTTPException(403, "Office hours are set by teachers.")
    return ctx.member.teacher_id


def _meeting_teachers(ctx: Ctx, teacher_ids: list[str]) -> list[str]:
    """Teachers this member may invite: Coordinator = own department, Admin = anyone."""
    allow("" if ctx.member.role in ("admin", "coordinator") else "Meetings are planned by the Coordinator or the Admin.")
    known = {t.id: t for t in ctx.state.college.teachers}
    ids = list(dict.fromkeys(teacher_ids))
    if not 1 <= len(ids) <= 12:
        raise HTTPException(422, "Pick between 1 and 12 teachers.")
    for i in ids:
        if i not in known:
            raise HTTPException(404, "Teacher not found.")
        if ctx.member.role == "coordinator" and known[i].department_id != ctx.member.department_id:
            raise HTTPException(403, f"{known[i].name} is in another department; ask the College Admin.")
    return ids


# ---- office hours -----------------------------------------------------------------------------------

class OfficeHourIn(BaseModel):
    day: str
    start: str = Field(pattern=TIME)
    end: str = Field(pattern=TIME)
    seats: int = 3
    place: str = Field(default="", max_length=120)


class TeacherHours(BaseModel):
    teacher_id: str
    name: str
    department: str
    teaches_you: bool
    hours: list[OfficeHour]


@router.get("/office-hours", response_model=list[OfficeHour])
def my_office_hours(ctx: Ctx = Depends(org_ctx)) -> list[OfficeHour]:
    return bookings.office_hours(ctx.state.id, _teacher_id(ctx))


@router.post("/office-hours", response_model=list[OfficeHour], status_code=201)
def add_office_hour(body: OfficeHourIn, ctx: Ctx = Depends(org_ctx)) -> list[OfficeHour]:
    tid = _teacher_id(ctx)
    hour = OfficeHour(teacher_id=tid, day=body.day, start=body.start, end=body.end, seats=body.seats,
                      place=body.place.strip())
    why = bookings.add_office_hour(ctx.state.college, _tt(ctx), ctx.state.id, hour)
    if why:
        raise HTTPException(422, why)
    return bookings.office_hours(ctx.state.id, tid)


@router.delete("/office-hours/{hour_id}", response_model=list[OfficeHour])
def remove_office_hour(hour_id: str, ctx: Ctx = Depends(org_ctx)) -> list[OfficeHour]:
    tid = _teacher_id(ctx)
    if not any(h.id == hour_id for h in bookings.office_hours(ctx.state.id, tid)):
        raise HTTPException(404, "Office hour not found.")
    bookings.remove_office_hour(ctx.state.id, hour_id)
    return bookings.office_hours(ctx.state.id, tid)


@router.get("/teachers", response_model=list[TeacherHours])
def teachers_with_hours(ctx: Ctx = Depends(org_ctx)) -> list[TeacherHours]:
    """For students: teachers who hold office hours, their own teachers first."""
    st = _student(ctx)
    college, tt = ctx.state.college, _tt(ctx)
    mine = {s.teacher_id for s in bookings.student_classes(college, tt.sessions, st)} if tt else set()
    depts = {d.id: d.short for d in college.departments}
    hours = bookings.office_hours(ctx.state.id)
    out = []
    for t in college.teachers:
        th = [h for h in hours if h.teacher_id == t.id]
        if th:
            out.append(TeacherHours(teacher_id=t.id, name=t.name, department=depts.get(t.department_id, ""),
                                    teaches_you=t.id in mine, hours=th))
    return sorted(out, key=lambda x: (not x.teaches_you, x.name))


# ---- doubt slots ------------------------------------------------------------------------------------

class DoubtIn(BaseModel):
    office_hour_id: str
    date: str = Field(pattern=DATE)
    topic: str = Field(default="", max_length=200)


class BookResult(BaseModel):
    message: str
    booking: BookingOut


@router.get("/doubt-slots", response_model=list[Slot])
def doubt_slots(teacher_id: str | None = None, ctx: Ctx = Depends(org_ctx)) -> list[Slot]:
    st = _student(ctx)
    today, now = _today_now()
    return bookings.doubt_slots(ctx.state.college, _tt(ctx), ctx.state.id, st, today, now, teacher_id)


def _out(ctx: Ctx, booking_id: str) -> BookingOut:
    today, now = _today_now()
    items = bookings.listing(ctx.state.college, _tt(ctx), ctx.state.id, created_by=ctx.member.user_id,
                             teacher_id=ctx.member.teacher_id, today=today, now=now, include_past=True)
    found = next((b for b in items if b.id == booking_id), None)
    if found is None:  # e.g. a student's booking (matched by student id)
        st = next((s for s in ctx.state.college.students if s.email.lower() == ctx.member.email.lower()), None)
        items = bookings.listing(ctx.state.college, _tt(ctx), ctx.state.id, student_id=st.id if st else "-",
                                 today=today, now=now, include_past=True)
        found = next(b for b in items if b.id == booking_id)
    return found


@router.post("/doubt", response_model=BookResult, status_code=201)
def book_doubt(body: DoubtIn, ctx: Ctx = Depends(org_ctx)) -> BookResult:
    st = _student(ctx)
    today, now = _today_now()
    b, msg = bookings.book_doubt(ctx.state.college, _tt(ctx), ctx.state.id, st, body.office_hour_id, body.date,
                                 body.topic, ctx.member.user_id, ctx.member.name, today, now)
    if b is None:
        raise HTTPException(422, msg)
    send(ctx.state.id, f"Doubt slot booked: {st.name} ({b.section})",
         f"{bookings.label(b.date)} {b.start}-{b.end}" + (f" · {b.place}" if b.place else "") + f" · {b.title}",
         Audience(teacher_ids=b.teacher_ids), ctx.member.user_id, link="/bookings")
    return BookResult(message=msg, booking=_out(ctx, b.id))


# ---- meetings ---------------------------------------------------------------------------------------

class MeetingTimesIn(BaseModel):
    teacher_ids: list[str]
    from_date: str | None = Field(default=None, pattern=DATE)
    days: int = Field(default=7, ge=1, le=bookings.LOOKAHEAD_DAYS)
    periods: int = Field(default=1, ge=1, le=3)


class MeetingIn(BaseModel):
    teacher_ids: list[str]
    date: str = Field(pattern=DATE)
    start: str = Field(pattern=TIME)
    end: str = Field(pattern=TIME)
    title: str = Field(default="", max_length=200)
    place: str = Field(default="", max_length=120)


@router.post("/meeting-times", response_model=list[Slot])
def meeting_times(body: MeetingTimesIn, ctx: Ctx = Depends(org_ctx)) -> list[Slot]:
    ids = _meeting_teachers(ctx, body.teacher_ids)
    today, now = _today_now()
    return bookings.meeting_times(ctx.state.college, _tt(ctx), ctx.state.id, ids, body.from_date or today,
                                  body.days, body.periods, today, now)


@router.post("/meetings", response_model=BookResult, status_code=201)
def book_meeting(body: MeetingIn, ctx: Ctx = Depends(org_ctx)) -> BookResult:
    ids = _meeting_teachers(ctx, body.teacher_ids)
    today, now = _today_now()
    b, msg = bookings.book_meeting(ctx.state.college, _tt(ctx), ctx.state.id, ids, body.date, body.start, body.end,
                                   body.title, body.place, ctx.member.user_id, ctx.member.name, today, now)
    if b is None:
        raise HTTPException(422, msg)
    send(ctx.state.id, f"Meeting: {b.title}",
         f"{bookings.label(b.date)} {b.start}-{b.end}" + (f" · {b.place}" if b.place else "")
         + f" · booked by {ctx.member.name}", Audience(teacher_ids=b.teacher_ids), ctx.member.user_id, link="/bookings")
    return BookResult(message=msg, booking=_out(ctx, b.id))


# ---- my bookings ------------------------------------------------------------------------------------

@router.get("", response_model=list[BookingOut])
def my_bookings(include_past: bool = False, ctx: Ctx = Depends(org_ctx)) -> list[BookingOut]:
    """Students: their doubt slots. Teachers: everything with them. Coordinator / Admin: meetings they booked."""
    today, now = _today_now()
    m = ctx.member
    student_id = None
    if m.role == "student":
        student_id = _student(ctx).id
    return bookings.listing(ctx.state.college, _tt(ctx), ctx.state.id, teacher_id=m.teacher_id,
                            student_id=student_id, created_by=m.user_id, today=today, now=now,
                            include_past=include_past)


@router.post("/{booking_id}/cancel", response_model=list[BookingOut])
def cancel(booking_id: str, ctx: Ctx = Depends(org_ctx)) -> list[BookingOut]:
    m, org = ctx.member, ctx.state.id
    b = bookings.get(org, booking_id)
    st = next((s for s in ctx.state.college.students if s.email.lower() == m.email.lower()), None) \
        if m.role == "student" else None
    involved = b is not None and (
        b.created_by == m.user_id or (m.teacher_id is not None and m.teacher_id in b.teacher_ids)
        or (st is not None and b.student_id == st.id) or m.role == "admin")
    if not involved:
        raise HTTPException(404, "Booking not found.")
    done = bookings.cancel(org, booking_id, m.name)
    if done is None:
        raise HTTPException(409, "This booking is already cancelled.")
    when = f"{bookings.label(done.date)} {done.start}-{done.end}"
    # Tell everyone else involved.
    if done.kind == "doubt":
        if st is not None:
            send(org, f"Doubt slot cancelled by {m.name}", f"{when} · {done.title}", Audience(teacher_ids=done.teacher_ids),
                 m.user_id, link="/bookings")
        else:
            send(org, f"Your doubt slot was cancelled by {m.name}", f"{when} · {done.title}",
                 Audience(student_emails=[done.student_email]), m.user_id, link="/bookings")
    else:
        others = [t for t in done.teacher_ids if t != m.teacher_id]
        send(org, f"Meeting cancelled: {done.title}", f"{when} · cancelled by {m.name}", Audience(teacher_ids=others),
             m.user_id, link="/bookings")
    return my_bookings(ctx=ctx)
