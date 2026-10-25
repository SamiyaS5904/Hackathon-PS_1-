"""Teacher booking: office hours, doubt slots and meetings (V1 "building now" item 2).

- A teacher publishes weekly **office hours** (day, time, seats, place). Hours that overlap their own
  classes or blocked times are refused.
- A student books a **doubt slot**: one seat in an office hour on a real date. Offered only when the
  teacher has no class then that day (one-day changes included), seats are left, the student has no
  class then and it is not a holiday.
- A Department Coordinator (own department's teachers) or the College Admin books a **meeting** at a
  time when every chosen teacher is free: no class, no blocked time, no other booking, and inside each
  teacher's shift hours.

Bookings sit beside the timetable: they never move a class. If a later timetable change puts a class on
a booked time, the booking is shown with a clash warning (computed when read) and other times are offered.

Office hours and bookings live in memory (loaded per college on first use) and are saved by the
background writer, like attendance.
"""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import BookingRow, SessionLocal, new_id
from app.edits.oneday import active, label, weekday
from app.models.domain import College, Session, Student, Teacher, Timetable, to_minutes
from app.store import writer

LOOKAHEAD_DAYS = 14  # how far ahead doubt slots and meeting times are offered


class OfficeHour(BaseModel):
    id: str = Field(default_factory=new_id)
    teacher_id: str
    day: str  # Mon..Sun
    start: str  # HH:MM
    end: str
    seats: int = 3  # students per slot (a small group doubt session)
    place: str = ""  # e.g. "Staff room 2"


class Booking(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: str  # "doubt" | "meeting"
    date: str  # YYYY-MM-DD
    start: str
    end: str
    teacher_ids: list[str]
    title: str  # doubt: the topic; meeting: its title
    place: str = ""
    office_hour_id: str | None = None  # doubt slots
    student_id: str | None = None
    student_name: str = ""
    student_email: str = ""
    section: str = ""  # the student's section, for the teacher's list
    created_by: str  # user id
    created_by_name: str
    created_at: float = Field(default_factory=time.time)
    status: str = "booked"  # "booked" | "cancelled"
    cancelled_by: str = ""


class Slot(BaseModel):
    """A bookable time on a real date."""

    date: str
    label: str  # "Tue 28 Oct"
    start: str
    end: str
    teacher_id: str | None = None  # doubt slots
    teacher_name: str = ""
    office_hour_id: str | None = None
    place: str = ""
    seats_left: int | None = None


class BookingOut(Booking):
    label: str  # "Tue 28 Oct"
    teacher_names: list[str]
    clash: str | None = None  # set when a class now overlaps this booking
    past: bool = False


_lock = threading.Lock()
_hours: dict[str, dict[str, OfficeHour]] = {}  # org -> id -> office hour
_bookings: dict[str, dict[str, Booking]] = {}  # org -> id -> booking


def _load(org: str) -> tuple[dict[str, OfficeHour], dict[str, Booking]]:
    with _lock:
        if org in _hours:
            return _hours[org], _bookings[org]
    with SessionLocal() as db:
        rows = db.scalars(select(BookingRow).where(BookingRow.org_id == org)).all()
    hours = {r.id: OfficeHour(**r.data) for r in rows if r.kind == "office_hour"}
    books = {r.id: Booking(**r.data) for r in rows if r.kind == "booking"}
    with _lock:
        return _hours.setdefault(org, hours), _bookings.setdefault(org, books)


def _save(org: str, kind: str, item: OfficeHour | Booking) -> None:
    data = item.model_dump()

    def put(db) -> None:
        row = db.get(BookingRow, item.id)
        if row is None:
            db.add(BookingRow(id=item.id, org_id=org, kind=kind, data=data))
        else:
            row.data = data

    writer.submit(put)


def _drop(item_id: str) -> None:
    def rm(db) -> None:
        row = db.get(BookingRow, item_id)
        if row is not None:
            db.delete(row)

    writer.submit(rm)


# ---- time helpers -----------------------------------------------------------------------------------

def _overlaps(a0: str, a1: str, b0: str, b1: str) -> bool:
    return to_minutes(a0) < to_minutes(b1) and to_minutes(b0) < to_minutes(a1)


def _dates(college: College, start: str, days: int) -> list[str]:
    """Working, non-holiday dates from ``start`` (inclusive)."""
    d0 = date.fromisoformat(start)
    holidays = {h.date for h in college.holidays}
    out = []
    for i in range(days):
        d = (d0 + timedelta(days=i)).isoformat()
        if weekday(college, d) and d not in holidays:
            out.append(d)
    return out


def _upcoming(d: str, start: str, today: str, now: str) -> bool:
    return d > today or (d == today and to_minutes(start) > to_minutes(now))


def student_classes(college: College, sessions: list[Session], st: Student) -> list[Session]:
    """The student's own classes among ``sessions``: section (and lab batch) classes and elective groups."""
    out = []
    for s in sessions:
        if s.elective_slot_id:
            if st.id in college.elective_group(s.elective_slot_id, s.group_id).student_ids:
                out.append(s)
        elif st.section_id in s.section_ids and (s.batch_id is None or s.batch_id == st.batch_id):
            out.append(s)
    return out


def _class_text(college: College, s: Session) -> str:
    subj = college.subject(s.subject_id)
    secs = " + ".join(college.section(i).name for i in s.section_ids)
    return f"{subj.name} ({secs}) {s.start}-{s.end}"


def teacher_busy(college: College, tt: Timetable | None, org: str, t: Teacher, d: str, start: str, end: str,
                 ignore_booking: str | None = None, office_hour: str | None = None) -> str | None:
    """Why teacher ``t`` can't be booked on date ``d`` from ``start`` to ``end`` (None = free).
    Doubt slots booked in ``office_hour`` don't count: that hour is shared by several students."""
    if tt is not None:
        for s in active(college, tt, d):
            if s.teacher_id == t.id and _overlaps(s.start, s.end, start, end):
                return f"{t.name} teaches {_class_text(college, s)}"
    wd = weekday(college, d)
    for b in t.blocked:
        if b.day == wd and _overlaps(b.start, b.end, start, end):
            return f"{t.name} is unavailable {b.start}-{b.end}"
    _, books = _load(org)
    for b in books.values():
        if (b.status != "booked" or b.id == ignore_booking or t.id not in b.teacher_ids or b.date != d
                or not _overlaps(b.start, b.end, start, end)):
            continue
        if b.kind == "meeting":
            return f"{t.name} has the meeting \"{b.title}\" {b.start}-{b.end}"
        if office_hour is None or b.office_hour_id != office_hour:
            return f"{t.name} has a doubt session with {b.student_name} {b.start}-{b.end}"
    return None


def _in_shift_hours(college: College, t: Teacher, start: str, end: str) -> bool:
    for sid in t.shift_ids:
        periods = college.shift(sid).periods
        if periods and to_minutes(periods[0].start) <= to_minutes(start) and to_minutes(end) <= to_minutes(periods[-1].end):
            return True
    return False


# ---- office hours -----------------------------------------------------------------------------------

def office_hours(org: str, teacher_id: str | None = None) -> list[OfficeHour]:
    hours, _ = _load(org)
    order = {d: i for i, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])}
    out = [h for h in hours.values() if teacher_id is None or h.teacher_id == teacher_id]
    return sorted(out, key=lambda h: (order.get(h.day, 9), h.start))


def add_office_hour(college: College, tt: Timetable | None, org: str, hour: OfficeHour) -> str | None:
    """Save a weekly office hour; returns a plain-language reason when it isn't possible."""
    if hour.day not in college.days:
        return f"{hour.day} isn't a working day."
    if to_minutes(hour.start) >= to_minutes(hour.end):
        return "The office hour must end after it starts."
    if not 1 <= hour.seats <= 30:
        return "Seats must be between 1 and 30."
    t = college.teacher(hour.teacher_id)
    if tt is not None:
        for s in tt.sessions:
            if s.teacher_id == t.id and s.day == hour.day and _overlaps(s.start, s.end, hour.start, hour.end):
                return f"You teach {_class_text(college, s)} on {hour.day}. Pick a free period."
    for b in t.blocked:
        if b.day == hour.day and _overlaps(b.start, b.end, hour.start, hour.end):
            return f"You marked {hour.day} {b.start}-{b.end} as unavailable."
    hours, _ = _load(org)
    for h in hours.values():
        if h.teacher_id == t.id and h.day == hour.day and _overlaps(h.start, h.end, hour.start, hour.end):
            return f"You already have office hours on {h.day} {h.start}-{h.end}."
    with _lock:
        hours[hour.id] = hour
    _save(org, "office_hour", hour)
    return None


def remove_office_hour(org: str, hour_id: str) -> OfficeHour | None:
    """Remove an office hour. Doubt slots already booked in it stay booked."""
    hours, _ = _load(org)
    with _lock:
        hour = hours.pop(hour_id, None)
    if hour is not None:
        _drop(hour_id)
    return hour


# ---- doubt slots ------------------------------------------------------------------------------------

def _seats_taken(org: str, hour_id: str, d: str) -> int:
    _, books = _load(org)
    return sum(1 for b in books.values() if b.status == "booked" and b.office_hour_id == hour_id and b.date == d)


def _student_busy(college: College, tt: Timetable | None, org: str, st: Student, d: str, start: str,
                  end: str) -> str | None:
    if tt is not None:
        for s in student_classes(college, active(college, tt, d), st):
            if _overlaps(s.start, s.end, start, end):
                return f"you have {college.subject(s.subject_id).name} {s.start}-{s.end}"
    _, books = _load(org)
    for b in books.values():
        if b.status == "booked" and b.student_id == st.id and b.date == d and _overlaps(b.start, b.end, start, end):
            return f"you already booked \"{b.title}\" {b.start}-{b.end}"
    return None


def doubt_slots(college: College, tt: Timetable | None, org: str, st: Student, today: str, now: str,
                teacher_id: str | None = None) -> list[Slot]:
    """Open doubt slots for a student over the next two weeks (one teacher, or every teacher)."""
    hours = [h for h in office_hours(org, teacher_id)]
    names = {t.id: t for t in college.teachers}
    out: list[Slot] = []
    for d in _dates(college, today, LOOKAHEAD_DAYS):
        wd = weekday(college, d)
        for h in hours:
            if h.day != wd or h.teacher_id not in names or not _upcoming(d, h.start, today, now):
                continue
            left = h.seats - _seats_taken(org, h.id, d)
            if left <= 0:
                continue
            if teacher_busy(college, tt, org, names[h.teacher_id], d, h.start, h.end, office_hour=h.id):
                continue  # e.g. a makeup class was moved onto the office hour that day
            if _student_busy(college, tt, org, st, d, h.start, h.end):
                continue
            out.append(Slot(date=d, label=label(d), start=h.start, end=h.end, teacher_id=h.teacher_id,
                            teacher_name=names[h.teacher_id].name, office_hour_id=h.id, place=h.place,
                            seats_left=left))
    return out


def book_doubt(college: College, tt: Timetable | None, org: str, st: Student, hour_id: str, d: str, topic: str,
               user_id: str, user_name: str, today: str, now: str) -> tuple[Booking | None, str]:
    hours, books = _load(org)
    h = hours.get(hour_id)
    if h is None:
        return None, "That office hour no longer exists."
    if weekday(college, d) != h.day or any(x.date == d for x in college.holidays):
        return None, "That date doesn't match the office hour."
    if not _upcoming(d, h.start, today, now):
        return None, "That time has already passed."
    if h.seats - _seats_taken(org, h.id, d) <= 0:
        return None, "That slot is full. Pick another time."
    t = college.teacher(h.teacher_id)
    why = teacher_busy(college, tt, org, t, d, h.start, h.end, office_hour=h.id) or _student_busy(college, tt, org, st, d, h.start, h.end)
    if why:
        return None, f"Not possible: {why}."
    b = Booking(kind="doubt", date=d, start=h.start, end=h.end, teacher_ids=[t.id], title=topic.strip()[:200] or "Doubts",
                place=h.place, office_hour_id=h.id, student_id=st.id, student_name=st.name, student_email=st.email,
                section=college.section(st.section_id).name, created_by=user_id, created_by_name=user_name)
    with _lock:
        books[b.id] = b
    _save(org, "booking", b)
    return b, f"Booked: {t.name}, {label(d)} {h.start}-{h.end}" + (f", {h.place}" if h.place else "") + "."


# ---- meetings ---------------------------------------------------------------------------------------

def meeting_times(college: College, tt: Timetable | None, org: str, teacher_ids: list[str], start_date: str,
                  days: int, periods: int, today: str, now: str, limit: int = 40) -> list[Slot]:
    """Times when every chosen teacher is free, inside each teacher's shift hours.

    Candidate windows are ``periods`` consecutive periods of the teachers' shifts (so meetings line up
    with the bell), earliest first."""
    teachers = [college.teacher(i) for i in teacher_ids]
    windows: set[tuple[str, str]] = set()
    for sid in {sid for t in teachers for sid in t.shift_ids}:
        ps = college.shift(sid).periods
        for i in range(len(ps) - periods + 1):
            windows.add((ps[i].start, ps[i + periods - 1].end))
    ordered = sorted(windows, key=lambda w: (to_minutes(w[0]), to_minutes(w[1])))
    out: list[Slot] = []
    for d in _dates(college, max(start_date, today), days):
        for a, b in ordered:
            if not _upcoming(d, a, today, now):
                continue
            if not all(_in_shift_hours(college, t, a, b) for t in teachers):
                continue
            if any(teacher_busy(college, tt, org, t, d, a, b) for t in teachers):
                continue
            out.append(Slot(date=d, label=label(d), start=a, end=b))
            if len(out) >= limit:
                return out
    return out


def book_meeting(college: College, tt: Timetable | None, org: str, teacher_ids: list[str], d: str, start: str,
                 end: str, title: str, place: str, user_id: str, user_name: str, today: str,
                 now: str) -> tuple[Booking | None, str]:
    if not teacher_ids:
        return None, "Pick at least one teacher."
    if not _upcoming(d, start, today, now):
        return None, "That time has already passed."
    if weekday(college, d) is None or any(x.date == d for x in college.holidays):
        return None, "That isn't a working day."
    teachers = [college.teacher(i) for i in teacher_ids]
    for t in teachers:
        why = teacher_busy(college, tt, org, t, d, start, end)
        if why:
            return None, f"Not possible: {why}."
    _, books = _load(org)
    b = Booking(kind="meeting", date=d, start=start, end=end, teacher_ids=list(dict.fromkeys(teacher_ids)),
                title=title.strip()[:200] or "Meeting", place=place.strip()[:120], created_by=user_id,
                created_by_name=user_name)
    with _lock:
        books[b.id] = b
    _save(org, "booking", b)
    return b, f"Meeting booked: {label(d)} {start}-{end} with {', '.join(t.name for t in teachers)}."


# ---- listing and cancelling -------------------------------------------------------------------------

def get(org: str, booking_id: str) -> Booking | None:
    return _load(org)[1].get(booking_id)


def cancel(org: str, booking_id: str, by: str) -> Booking | None:
    _, books = _load(org)
    b = books.get(booking_id)
    if b is None or b.status != "booked":
        return None
    b = b.model_copy(update={"status": "cancelled", "cancelled_by": by})
    with _lock:
        books[b.id] = b
    _save(org, "booking", b)
    return b


def listing(college: College, tt: Timetable | None, org: str, *, teacher_id: str | None = None,
            student_id: str | None = None, created_by: str | None = None, today: str, now: str,
            include_past: bool = False) -> list[BookingOut]:
    """Bookings that concern someone (any filter matches), soonest first, with live clash checks."""
    _, books = _load(org)
    names = {t.id: t.name for t in college.teachers}
    students = {s.id: s for s in college.students}
    out = []
    for b in books.values():
        mine = (teacher_id is not None and teacher_id in b.teacher_ids) or \
               (student_id is not None and b.student_id == student_id) or \
               (created_by is not None and b.created_by == created_by)
        if not mine:
            continue
        past = not _upcoming(b.date, b.end, today, now)
        if past and not include_past:
            continue
        clash = None
        if b.status == "booked" and not past:
            for tid in b.teacher_ids:
                t = next((x for x in college.teachers if x.id == tid), None)
                if t is not None:
                    clash = teacher_busy(college, tt, org, t, b.date, b.start, b.end, ignore_booking=b.id,
                                         office_hour=b.office_hour_id)
                    if clash:
                        break
            if clash is None and b.student_id in students:
                why = _student_busy(college, tt, org, students[b.student_id], b.date, b.start, b.end)
                if why and not why.startswith("you already booked"):
                    clash = f"The student now has a class: {why.removeprefix('you have ')}"
        out.append(BookingOut(**b.model_dump(), label=label(b.date),
                              teacher_names=[names.get(t, t) for t in b.teacher_ids], clash=clash, past=past))
    return sorted(out, key=lambda x: (x.status != "booked", x.date, x.start))
