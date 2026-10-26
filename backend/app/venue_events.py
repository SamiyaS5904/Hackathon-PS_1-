"""Room booking for events: a teacher (or Coordinator / Admin) books a free room on a real date.

- **Free rooms only**: no class there at that time on that date (one-day changes included), no other
  approved or waiting event, a working day and not a holiday. A class is never bumped.
- The request goes to whoever looks after the room: the Department Coordinator of the room's
  department, or the College Admin for shared rooms. The Admin (any room) and a Coordinator (own
  department's rooms) are approved straight away when they book themselves.
- An **approved** event holds the room for that date: one-day moves, makeup classes and other events
  can't take it (app/edits/oneday.py asks ``holds`` through its ``room_holds`` hook). A later weekly
  change that puts a class there is shown as a clash on the event, never hidden.

Events live in memory (loaded per college on first use) and are saved by the background writer, in
their own table.
"""

from __future__ import annotations

import threading
import time
from datetime import date as Date

from pydantic import BaseModel, Field
from sqlalchemy import JSON, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from app.accounts import Member
from app.db.models import Base, SessionLocal, new_id
from app.edits import oneday
from app.edits.oneday import active, label, weekday
from app.models.domain import College, Timetable, to_minutes
from app.notify import Audience
from app.store import writer


class VenueEventRow(Base):
    """One room booking for an event; the fields live in ``data`` (see ``VenueEvent``)."""

    __tablename__ = "venue_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class VenueEvent(BaseModel):
    id: str = Field(default_factory=new_id)
    venue_id: str
    date: str  # YYYY-MM-DD
    start: str  # HH:MM
    end: str
    title: str  # what the event is ("Coding contest")
    club: str = ""  # who runs it ("Coding Club")
    requested_by: str  # user id
    requested_by_name: str
    requester_role: str  # admin | coordinator | teacher
    requester_teacher_id: str | None = None
    requester_department_id: str | None = None
    owner_department_id: str | None = None  # the room's department; None = shared (College Admin decides)
    status: str = "pending"  # pending | approved | declined | cancelled
    decided_by: str = ""
    decided_at: float | None = None
    note: str = ""  # Coordinator's / Admin's note when declining
    created_at: float = Field(default_factory=time.time)


class EventOut(VenueEvent):
    label: str  # "Tue 28 Oct"
    venue: str
    capacity: int
    approver: str  # "CSE Coordinator" / "College Admin"
    can_decide: bool = False
    can_cancel: bool = False
    clash: str | None = None  # a class now uses the room then (a later weekly change)
    past: bool = False


class FreeVenue(BaseModel):
    venue_id: str
    name: str
    type: str
    capacity: int
    owner: str  # department short name or "Shared"
    approver: str  # who approves the booking


_lock = threading.Lock()
_events: dict[str, dict[str, VenueEvent]] = {}  # org -> id -> event


def _load(org: str) -> dict[str, VenueEvent]:
    with _lock:
        if org in _events:
            return _events[org]
    with SessionLocal() as db:
        rows = db.scalars(select(VenueEventRow).where(VenueEventRow.org_id == org)).all()
    items = {r.id: VenueEvent(**r.data) for r in rows}
    with _lock:
        return _events.setdefault(org, items)


def _save(org: str, ev: VenueEvent) -> None:
    data = ev.model_dump()

    def put(db) -> None:
        row = db.get(VenueEventRow, ev.id)
        if row is None:
            db.add(VenueEventRow(id=ev.id, org_id=org, data=data))
        else:
            row.data = data

    writer.submit(put)


def _put(org: str, ev: VenueEvent) -> VenueEvent:
    items = _load(org)
    with _lock:
        items[ev.id] = ev
    _save(org, ev)
    return ev


def get(org: str, event_id: str) -> VenueEvent | None:
    return _load(org).get(event_id)


# ---- the hold: approved events keep their room on their date --------------------------------------

def _overlaps(a0: str, a1: str, b0: str, b1: str) -> bool:
    return to_minutes(a0) < to_minutes(b1) and to_minutes(b0) < to_minutes(a1)


def holds(college: College, d: str) -> list[tuple[str, str, str, str]]:
    """Rooms held by approved events on date ``d``: (venue id, start, end, what)."""
    return [(e.venue_id, e.start, e.end, e.title + (f" ({e.club})" if e.club else ""))
            for e in _load(college.id).values() if e.status == "approved" and e.date == d]


oneday.room_holds = holds  # one-day moves and makeups never take a held room


# ---- finding and booking ----------------------------------------------------------------------------

def _approver(college: College, dept_id: str | None) -> str:
    if dept_id is None:
        return "College Admin"
    d = next((x for x in college.departments if x.id == dept_id), None)
    return f"{d.short if d else dept_id} Coordinator"


def _day_problem(college: College, d: str, start: str, end: str, today: str, now: str) -> str | None:
    try:
        Date.fromisoformat(d)
    except ValueError:
        return "Use a date like 2026-10-28."
    if to_minutes(start) >= to_minutes(end):
        return "The event must end after it starts."
    if d < today or (d == today and to_minutes(start) <= to_minutes(now)):
        return "That time has already passed."
    hol = next((h.label for h in college.holidays if h.date == d), None)
    if hol:
        return f"{label(d)} is a holiday ({hol})."
    if weekday(college, d) is None:
        return f"{label(d)} isn't a working day."
    return None


def room_busy(college: College, tt: Timetable | None, org: str, venue_id: str, d: str, start: str, end: str,
              ignore: str | None = None, pending_too: bool = True) -> str | None:
    """Why room ``venue_id`` can't be booked then (None = free). Classes on that real date (one-day
    changes included) and other events (approved, and waiting ones when ``pending_too``)."""
    if tt is not None:
        for s in active(college, tt, d):
            if s.venue_id == venue_id and _overlaps(s.start, s.end, start, end):
                secs = " + ".join(college.section(i).name for i in s.section_ids)
                return f"{college.subject(s.subject_id).name} ({secs}) is there {s.start}-{s.end}"
    for e in _load(org).values():
        if e.id == ignore or e.venue_id != venue_id or e.date != d or not _overlaps(e.start, e.end, start, end):
            continue
        if e.status == "approved" or (pending_too and e.status == "pending"):
            what = "booked" if e.status == "approved" else "requested"
            return f"\"{e.title}\" has it {what} {e.start}-{e.end}"
    return None


def free_venues(college: College, tt: Timetable | None, org: str, d: str, start: str, end: str, today: str,
                now: str, min_seats: int = 0) -> tuple[list[FreeVenue], str | None]:
    why = _day_problem(college, d, start, end, today, now)
    if why:
        return [], why
    depts = {x.id: x.short for x in college.departments}
    out = []
    for v in sorted(college.venues, key=lambda v: (v.capacity, v.name)):
        if v.capacity < min_seats or room_busy(college, tt, org, v.id, d, start, end):
            continue
        out.append(FreeVenue(venue_id=v.id, name=v.name, type=v.type.value, capacity=v.capacity,
                             owner=depts.get(v.department_id or "", "Shared"),
                             approver=_approver(college, v.department_id)))
    return out, None


def can_decide(m: Member, ev: VenueEvent) -> str:
    if m.role == "admin":
        return ""
    if m.role == "coordinator" and ev.owner_department_id is not None and ev.owner_department_id == m.department_id:
        return ""
    if ev.owner_department_id is None:
        return "Shared rooms are approved by the College Admin."
    return "Only the Coordinator of the room's department (or the College Admin) approves this."


def request(college: College, tt: Timetable | None, org: str, m: Member, venue_id: str, d: str, start: str,
            end: str, title: str, club: str, today: str, now: str) -> tuple[VenueEvent | None, str]:
    if m.role not in ("admin", "coordinator", "teacher"):
        return None, "Rooms for events are booked by teachers and staff."
    v = next((x for x in college.venues if x.id == venue_id), None)
    if v is None:
        return None, "Room not found."
    why = _day_problem(college, d, start, end, today, now) or room_busy(college, tt, org, v.id, d, start, end)
    if why:
        return None, f"Not possible: {why}."
    if not title.strip():
        return None, "Say what the event is."
    ev = VenueEvent(venue_id=v.id, date=d, start=start, end=end, title=title.strip()[:120], club=club.strip()[:80],
                    requested_by=m.user_id, requested_by_name=m.name, requester_role=m.role,
                    requester_teacher_id=m.teacher_id, requester_department_id=m.department_id,
                    owner_department_id=v.department_id)
    if not can_decide(m, ev):  # booking a room you look after yourself: approved straight away
        ev.status, ev.decided_by, ev.decided_at = "approved", m.name, time.time()
        _put(org, ev)
        return ev, f"Booked: {v.name}, {label(d)} {start}-{end}. The room is held for your event."
    _put(org, ev)
    return ev, f"Request sent to the {_approver(college, v.department_id)}: {v.name}, {label(d)} {start}-{end}."


def decide(college: College, tt: Timetable | None, org: str, m: Member, ev: VenueEvent, approve: bool,
           note: str = "") -> tuple[VenueEvent | None, str]:
    if ev.status != "pending":
        return None, f"This request is already {ev.status}."
    if approve:
        why = room_busy(college, tt, org, ev.venue_id, ev.date, ev.start, ev.end, ignore=ev.id, pending_too=False)
        if why:
            return None, f"The room isn't free any more: {why}. Decline it with a note."
    ev = ev.model_copy(update={"status": "approved" if approve else "declined", "decided_by": m.name,
                               "decided_at": time.time(), "note": note.strip()[:300]})
    _put(org, ev)
    return ev, "Approved: the room is held for the event." if approve else "Declined."


def cancel(org: str, m: Member, ev: VenueEvent) -> tuple[VenueEvent | None, str]:
    if ev.status not in ("pending", "approved"):
        return None, f"This booking is already {ev.status}."
    if ev.requested_by != m.user_id and m.role != "admin":
        return None, "Only the person who booked it (or the College Admin) can cancel it."
    ev = ev.model_copy(update={"status": "cancelled", "decided_by": m.name, "decided_at": time.time()})
    _put(org, ev)
    return ev, "Cancelled: the room is free again."


def requester_audience(ev: VenueEvent) -> Audience:
    if ev.requester_role == "teacher" and ev.requester_teacher_id:
        return Audience(teacher_ids=[ev.requester_teacher_id])
    if ev.requester_role == "coordinator" and ev.requester_department_id:
        return Audience(coordinator_departments=[ev.requester_department_id])
    return Audience(roles=["admin"])


def approver_audience(ev: VenueEvent) -> Audience:
    if ev.owner_department_id is None:
        return Audience(roles=["admin"])
    return Audience(coordinator_departments=[ev.owner_department_id])


# ---- listing ----------------------------------------------------------------------------------------

def out(college: College, tt: Timetable | None, org: str, m: Member, ev: VenueEvent, today: str,
        now: str) -> EventOut:
    v = next((x for x in college.venues if x.id == ev.venue_id), None)
    past = ev.date < today or (ev.date == today and to_minutes(ev.end) <= to_minutes(now))
    clash = None
    if ev.status == "approved" and not past and tt is not None:
        clash = next((f"{college.subject(s.subject_id).name} now uses the room {s.start}-{s.end}"
                      for s in active(college, tt, ev.date)
                      if s.venue_id == ev.venue_id and _overlaps(s.start, s.end, ev.start, ev.end)), None)
    return EventOut(**ev.model_dump(), label=label(ev.date), venue=v.name if v else "(room removed)",
                    capacity=v.capacity if v else 0, approver=_approver(college, ev.owner_department_id),
                    can_decide=ev.status == "pending" and not can_decide(m, ev),
                    can_cancel=ev.status in ("pending", "approved") and not past
                    and (ev.requested_by == m.user_id or m.role == "admin"),
                    clash=clash, past=past)


class EventLists(BaseModel):
    to_review: list[EventOut]  # waiting for this member's decision
    mine: list[EventOut]  # booked by this member
    upcoming: list[EventOut]  # approved events in rooms this member looks after


def listing(college: College, tt: Timetable | None, org: str, m: Member, today: str, now: str) -> EventLists:
    items = sorted(_load(org).values(), key=lambda e: (e.date, e.start))
    outs = [out(college, tt, org, m, e, today, now) for e in items]
    to_review = [e for e in outs if e.can_decide and not e.past]
    mine = [e for e in outs if e.requested_by == m.user_id and not (e.past and e.status != "approved")][-50:]
    looks_after = (lambda e: True) if m.role == "admin" else (
        lambda e: m.role == "coordinator" and e.owner_department_id == m.department_id)
    upcoming = [e for e in outs if e.status == "approved" and not e.past and looks_after(e)
                and e.requested_by != m.user_id]
    return EventLists(to_review=to_review, mine=mine, upcoming=upcoming)
