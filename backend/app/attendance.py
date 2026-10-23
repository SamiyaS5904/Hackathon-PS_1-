"""Attendance: teachers mark each class on a real date; students see where they stand against the rule.

One record per class occurrence (``occurrence_id`` = "<session id>@<original date>", stable even when
the class was moved for a day). It stores the roster as it was that day and who was absent, so
history stays right if sections change later. Only classes that were held and marked count; a
cancelled class is never "held".

Records live in memory (loaded per college on first use) and are saved by the background writer.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import AttendanceRow, SessionLocal
from app.models.domain import College, Session, Student
from app.store import writer

EDIT_DAYS = 7  # teachers can mark or correct a class up to a week later


@dataclass
class Record:
    occurrence_id: str
    session_id: str
    subject_id: str
    date: str
    roster: list[str]
    absent: list[str]
    marked_by: str
    marked_at: float


_lock = threading.Lock()
_records: dict[str, dict[str, Record]] = {}  # org -> occurrence id -> record


def _all(org: str) -> dict[str, Record]:
    with _lock:
        if org in _records:
            return _records[org]
    with SessionLocal() as db:
        rows = db.scalars(select(AttendanceRow).where(AttendanceRow.org_id == org)).all()
    loaded = {r.occurrence_id: Record(r.occurrence_id, r.session_id, r.subject_id, r.date, list(r.roster),
                                      list(r.absent), r.marked_by, r.marked_at) for r in rows}
    with _lock:
        return _records.setdefault(org, loaded)


def roster(college: College, s: Session) -> list[Student]:
    """Who is expected in this class: an elective group's members, a lab batch, or the whole section(s)."""
    if s.elective_slot_id:
        members = set(college.elective_group(s.elective_slot_id, s.group_id).student_ids)
        return [st for st in college.students if st.id in members]
    if s.batch_id:
        return [st for st in college.students if st.batch_id == s.batch_id]
    return [st for st in college.students if st.section_id in s.section_ids]


def get(org: str, occurrence_id: str) -> Record | None:
    return _all(org).get(occurrence_id)


def save(org: str, rec: Record) -> None:
    records = _all(org)
    with _lock:
        records[rec.occurrence_id] = rec
    row = dict(org_id=org, occurrence_id=rec.occurrence_id, session_id=rec.session_id, subject_id=rec.subject_id,
               date=rec.date, roster=rec.roster, absent=rec.absent, marked_by=rec.marked_by, marked_at=rec.marked_at)

    def put(db) -> None:
        existing = db.get(AttendanceRow, (org, rec.occurrence_id))
        if existing is None:
            db.add(AttendanceRow(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)

    writer.submit(put)


def new_record(occurrence_id: str, s: Session, date: str, roster_ids: list[str], absent: list[str],
               by: str) -> Record:
    return Record(occurrence_id, s.id, s.subject_id, date, roster_ids, sorted(set(absent) & set(roster_ids)), by,
                  time.time())


# ---- where a student stands ------------------------------------------------------

class SubjectAttendance(BaseModel):
    subject_id: str
    code: str
    name: str
    held: int
    attended: int
    percent: float | None  # None until a class was held
    status: str  # "ok" | "low" | "none"
    advice: str


class RecentMark(BaseModel):
    date: str
    subject: str
    present: bool


class StudentAttendance(BaseModel):
    min_percent: int
    held: int
    attended: int
    percent: float | None
    status: str
    advice: str
    subjects: list[SubjectAttendance]
    recent: list[RecentMark]


def advice(attended: int, held: int, minimum: int) -> tuple[str, str]:
    """('ok'|'low'|'none', plain sentence): how many classes can be missed, or must be attended in a row."""
    if held == 0:
        return "none", "No classes marked yet."
    pct = 100 * attended / held
    if pct >= minimum:
        can_miss = math.floor(attended * 100 / minimum - held) if minimum else held
        if can_miss <= 0:
            return "ok", f"At {minimum}% exactly: don't miss the next class."
        return "ok", f"You can miss {can_miss} more class{'es' if can_miss != 1 else ''} and stay at {minimum}%."
    need = math.ceil((minimum * held - 100 * attended) / (100 - minimum)) if minimum < 100 else held
    return "low", f"Below {minimum}%: attend the next {need} class{'es' if need != 1 else ''} in a row to get back."


def for_student(college: College, org: str, student_id: str) -> StudentAttendance:
    minimum = college.attendance_min_percent
    subjects = {s.id: s for s in college.subjects}
    per: dict[str, list[int]] = {}
    recent: list[tuple[str, str, bool]] = []
    for rec in _all(org).values():
        if student_id not in rec.roster:
            continue
        present = student_id not in rec.absent
        held_attended = per.setdefault(rec.subject_id, [0, 0])
        held_attended[0] += 1
        held_attended[1] += int(present)
        recent.append((rec.date, rec.subject_id, present))
    rows = []
    for sid, (held, attended) in sorted(per.items(), key=lambda kv: subjects[kv[0]].code if kv[0] in subjects else kv[0]):
        status, text = advice(attended, held, minimum)
        subj = subjects.get(sid)
        rows.append(SubjectAttendance(subject_id=sid, code=subj.code if subj else sid, name=subj.name if subj else sid,
                                      held=held, attended=attended, percent=round(100 * attended / held, 1),
                                      status=status, advice=text))
    held = sum(h for h, _ in per.values())
    attended = sum(a for _, a in per.values())
    status, text = advice(attended, held, minimum)
    recent.sort(reverse=True)
    return StudentAttendance(
        min_percent=minimum, held=held, attended=attended,
        percent=round(100 * attended / held, 1) if held else None, status=status, advice=text, subjects=rows,
        recent=[RecentMark(date=d, subject=subjects[s].name if s in subjects else s, present=p) for d, s, p in recent[:12]])


class StudentRow(BaseModel):
    student_id: str
    roll_no: str
    name: str
    held: int
    attended: int
    percent: float | None
    low: bool


def for_section(college: College, org: str, section_id: str) -> list[StudentRow]:
    """Everyone in a section with their overall attendance; below-rule students first."""
    minimum = college.attendance_min_percent
    counts: dict[str, list[int]] = {}
    for rec in _all(org).values():
        for st in rec.roster:
            c = counts.setdefault(st, [0, 0])
            c[0] += 1
            c[1] += int(st not in rec.absent)
    out = []
    for st in (x for x in college.students if x.section_id == section_id):
        held, attended = counts.get(st.id, [0, 0])
        pct = round(100 * attended / held, 1) if held else None
        out.append(StudentRow(student_id=st.id, roll_no=st.roll_no, name=st.name, held=held, attended=attended,
                              percent=pct, low=pct is not None and pct < minimum))
    return sorted(out, key=lambda r: (not r.low, r.roll_no))
