"""What staff need first thing in the morning, and how far a new college's setup has come.

- ``today_report``: teachers away (none of their classes happen today), classes that won't happen
  (cancelled), classes moved, the latest changes and the timetable's status. A Department Coordinator
  sees only their own department.
- ``setup_status``: the setup checklist (college details → departments → teachers & subjects → rooms →
  classes uploaded → generate → publish), each step with what is missing and where to fix it.
- ``locate``: links a data problem (from the pre-generation check) to the page where it can be fixed.
"""

from __future__ import annotations

import time

from pydantic import BaseModel

from app import change_requests
from app.edits.oneday import label, occurrences, weekday
from app.models.domain import College, Session, VenueType
from app.store import OrgState


class ClassLine(BaseModel):
    session_id: str
    occurrence_id: str
    subject: str
    sections: str
    teacher_id: str
    teacher: str
    start: str
    end: str
    room: str
    note: str = ""


class AwayTeacher(BaseModel):
    teacher_id: str
    name: str
    classes: int  # classes they had today


class RecentChange(BaseModel):
    id: str
    at: float
    actor: str
    action: str
    source: str
    undone: bool


class TodayStatus(BaseModel):
    state: str  # "none" | "draft" | "published" | "out_of_date"
    published_at: float | None = None
    published_by: str = ""


class TodayReport(BaseModel):
    date: str
    label: str
    working: bool
    holiday: str | None = None
    classes_today: int
    away: list[AwayTeacher]
    cancelled: list[ClassLine]  # won't happen today
    moved: list[ClassLine]  # moved to or away from today
    recent: list[RecentChange]
    status: TodayStatus
    pending_requests: int


def _line(college: College, s: Session, occurrence_id: str, note: str = "") -> ClassLine:
    t = next((x for x in college.teachers if x.id == s.teacher_id), None)
    v = next((x for x in college.venues if x.id == s.venue_id), None)
    return ClassLine(session_id=s.id, occurrence_id=occurrence_id, subject=college.subject(s.subject_id).name,
                     sections=" + ".join(college.section(i).name for i in s.section_ids), teacher_id=s.teacher_id,
                     teacher=t.name if t else s.teacher_id, start=s.start, end=s.end, room=v.name if v else "",
                     note=note)


def _status(st: OrgState) -> TodayStatus:
    tt = st.timetable
    if tt is None:
        return TodayStatus(state="none")
    pub = st.published
    if tt.college_revision != st.college.revision:
        state = "out_of_date"
    elif tt.published_at:
        state = "published"
    else:
        state = "draft"
    return TodayStatus(state=state, published_at=pub.published_at if pub else None,
                       published_by=pub.published_by if pub else "")


def today_report(st: OrgState, d: str, department_id: str | None = None) -> TodayReport:
    """``department_id`` limits the report to one department (a Coordinator's view)."""
    college = st.college
    hol = next((h.label for h in college.holidays if h.date == d), None)
    working = weekday(college, d) is not None and hol is None
    tt = st.published or st.timetable  # what really happens in class today
    occ = occurrences(college, tt, d) if tt is not None else []

    def mine(s: Session) -> bool:
        return department_id is None or any(college.section(i).department_id == department_id
                                            for i in s.section_ids)

    occ = [o for o in occ if mine(o.session)]
    cancelled = [_line(college, o.session, o.occurrence_id, o.note) for o in occ if o.status == "cancelled"]
    moved = [_line(college, o.session, o.occurrence_id, o.note) for o in occ if o.status in ("moved_in", "moved_out")]
    happening: dict[str, int] = {}
    total: dict[str, int] = {}
    for o in occ:
        total[o.session.teacher_id] = total.get(o.session.teacher_id, 0) + 1
        if o.status in ("normal", "moved_in"):
            happening[o.session.teacher_id] = happening.get(o.session.teacher_id, 0) + 1
    names = {t.id: t.name for t in college.teachers}
    away = [AwayTeacher(teacher_id=tid, name=names.get(tid, tid), classes=n)
            for tid, n in total.items() if n and not happening.get(tid)]
    recent = [RecentChange(id=e.id, at=e.at, actor=e.actor, action=e.action, source=e.source, undone=e.undone)
              for e in reversed(st.audit[-5:])]
    return TodayReport(
        date=d, label=label(d), working=working, holiday=hol,
        classes_today=sum(1 for o in occ if o.status in ("normal", "moved_in")),
        away=sorted(away, key=lambda a: a.name), cancelled=sorted(cancelled, key=lambda c: c.start),
        moved=sorted(moved, key=lambda c: c.start), recent=recent, status=_status(st),
        pending_requests=change_requests.pending_count(st.id, department_id))


# ---- setup checklist ----------------------------------------------------------------------------------

class SetupStep(BaseModel):
    key: str
    title: str
    done: bool
    missing: str = ""
    link: str


class SetupStatus(BaseModel):
    done: bool
    steps: list[SetupStep]


def setup_status(st: OrgState) -> SetupStatus:
    c = st.college
    tt = st.timetable
    depts = c.departments

    def dept_link(pred) -> str:
        bad = next((d for d in depts if pred(d.id)), None)
        return f"/departments/{bad.id}" if bad else "/departments"

    no_people = [d.short for d in depts
                 if not any(t.department_id == d.id for t in c.teachers)
                 or not any(s.department_id == d.id for s in c.subjects)]
    lecture_rooms = [v for v in c.venues if v.type != VenueType.lab]
    needs_lab = any(s.labs_per_week for s in c.subjects)
    labs = [v for v in c.venues if v.type == VenueType.lab]
    dept_of = {s.id: s.department_id for s in c.sections}
    # A department without sections of its own (e.g. Applied Sciences teaching first years) needs no classes.
    with_sections = {s.department_id for s in c.sections}
    without_classes = [d.short for d in depts if d.id in with_sections
                       and not any(dept_of.get(a.section_ids[0]) == d.id for a in c.allotments)]
    no_teacher = sum(1 for a in c.allotments if not a.teacher_id)
    not_ready = [d.short for d in depts if not (c.department_status.get(d.id) and c.department_status[d.id].ready)]
    details = c.setup_saved if c.setup_saved is not None else bool(depts)
    current = tt is not None and tt.college_revision == c.revision and bool(tt.sessions)

    steps = [
        SetupStep(key="details", title="College details", done=details,
                  missing="" if details else "Set the working days, shifts, periods and lunch window.",
                  link="/setup?step=week"),
        SetupStep(key="departments", title="Departments", done=bool(depts),
                  missing="" if depts else "Add at least one department.", link="/setup?step=departments"),
        SetupStep(key="people", title="Teachers & subjects", done=bool(depts) and not no_people,
                  missing=(f"No teachers or subjects yet in: {', '.join(no_people)}." if no_people
                           else "" if depts else "Add departments first."),
                  link=dept_link(lambda d: d in {x.id for x in depts if x.short in no_people})),
        SetupStep(key="rooms", title="Rooms", done=bool(lecture_rooms) and (bool(labs) or not needs_lab),
                  missing=("Add lecture rooms." if not lecture_rooms
                           else "Some subjects have labs but there is no lab room." if needs_lab and not labs else ""),
                  link="/setup?step=departments"),
        SetupStep(key="upload", title="Classes uploaded & Ready", done=bool(c.allotments) and not without_classes
                  and not no_teacher and not not_ready,
                  missing=(f"No classes yet in: {', '.join(without_classes)}." if without_classes
                           else f"{no_teacher} class(es) still need a teacher." if no_teacher
                           else f"Not marked Ready: {', '.join(not_ready)}." if not_ready
                           else "" if c.allotments else "Add departments first, then upload each one's Excel sheet."),
                  link=dept_link(lambda d: next((x.short for x in depts if x.id == d), "") in
                                 set(without_classes) | set(not_ready))),
        SetupStep(key="generate", title="Generate", done=current,
                  missing="" if current else ("The college data changed: regenerate." if tt is not None
                                              else "Generate the timetable."),
                  link="/timetable"),
        SetupStep(key="publish", title="Publish", done=current and bool(tt and tt.published_at),
                  missing="" if current and tt and tt.published_at else "Publish so teachers and students see it.",
                  link="/timetable"),
    ]
    return SetupStatus(done=all(s.done for s in steps), steps=steps)


# ---- where to fix a data problem ----------------------------------------------------------------------

class Problem(BaseModel):
    message: str
    link: str  # page to open
    where: str  # short label for the link, e.g. "CSE department"


def locate(college: College, message: str) -> Problem:
    """Best place to fix a pre-generation problem, found from the names it mentions."""
    low = message.lower()
    for s in sorted(college.sections, key=lambda x: -len(x.name)):
        if s.name.lower() in low:
            d = next((x for x in college.departments if x.id == s.department_id), None)
            return Problem(message=message, link=f"/departments/{s.department_id}",
                           where=f"{d.short if d else s.department_id} department")
    for t in sorted(college.teachers, key=lambda x: -len(x.name)):
        if t.name.lower() in low:
            d = next((x for x in college.departments if x.id == t.department_id), None)
            return Problem(message=message, link=f"/departments/{t.department_id}",
                           where=f"{d.short if d else t.department_id} department")
    if "mess window" in low or "shift" in low or "period" in low:
        return Problem(message=message, link="/setup?step=timings", where="Timings")
    if "room" in low or "lab" in low or "hall" in low:
        return Problem(message=message, link="/setup?step=departments", where="Rooms")
    if "rule" in low:
        return Problem(message=message, link="/rules", where="Rules")
    if "no teacher" in low:
        dept_of = {s.id: s.department_id for s in college.sections}
        a = next((a for a in college.allotments if not a.teacher_id), None)
        if a is not None:
            return Problem(message=message, link=f"/departments/{dept_of.get(a.section_ids[0], '')}",
                           where="Teacher suggestions")
    return Problem(message=message, link="/departments", where="Departments")


def now_date() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())

