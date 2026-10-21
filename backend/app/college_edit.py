"""Editing college data safely: college settings (Admin) and one department's slice (Coordinator).

Saving is refused only for *structural* errors (duplicate ids, references to things that
don't exist, bad times), because the solver relies on those. Incomplete data is allowed
and reported through the normal feasibility check.
"""

from __future__ import annotations

import re
import time

from pydantic import BaseModel

from app.models.domain import (
    Allotment,
    College,
    DepartmentStatus,
    Holiday,
    Section,
    Shift,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    Venue,
)

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Settings(BaseModel):
    days: list[str]
    lab_periods: int
    shifts: list[Shift]
    holidays: list[Holiday] = []
    semester_start: str | None = None
    semester_end: str | None = None


class DeptData(BaseModel):
    sections: list[Section] = []
    teachers: list[Teacher] = []
    subjects: list[Subject] = []
    venues: list[Venue] = []
    allotments: list[Allotment] = []
    teacher_subjects: list[TeacherSubject] = []
    students: list[Student] = []


def _m(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _time_ok(t: str) -> bool:
    return bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t))


def settings_of(college: College) -> Settings:
    return Settings(days=college.days, lab_periods=college.lab_periods, shifts=college.shifts,
                    holidays=college.holidays, semester_start=college.semester_start,
                    semester_end=college.semester_end)


def dept_slice(college: College, dept: str) -> DeptData:
    secs = {s.id for s in college.sections if s.department_id == dept}
    teachers = {t.id for t in college.teachers if t.department_id == dept}
    return DeptData(
        sections=[s for s in college.sections if s.department_id == dept],
        teachers=[t for t in college.teachers if t.department_id == dept],
        subjects=[s for s in college.subjects if s.department_id == dept],
        venues=[v for v in college.venues if v.department_id == dept],
        allotments=[a for a in college.allotments if set(a.section_ids) <= secs],
        teacher_subjects=[ts for ts in college.teacher_subjects if ts.teacher_id in teachers],
        students=[st for st in college.students if st.section_id in secs],
    )


def structural_errors(c: College) -> list[str]:
    errs: list[str] = []

    def dupes(kind: str, ids: list[str]) -> None:
        seen = set()
        for i in ids:
            if i in seen:
                errs.append(f"Two {kind} have the same id '{i}'.")
            seen.add(i)

    dupes("departments", [d.id for d in c.departments])
    dupes("shifts", [s.id for s in c.shifts])
    dupes("rooms", [v.id for v in c.venues])
    dupes("sections", [s.id for s in c.sections])
    dupes("batches", [b.id for s in c.sections for b in s.batches])
    dupes("teachers", [t.id for t in c.teachers])
    dupes("subjects", [s.id for s in c.subjects])
    dupes("classes", [a.id for a in c.allotments])
    dupes("students", [s.id for s in c.students])
    dupes("student emails", [s.email.lower() for s in c.students])

    if not c.days or any(d not in WEEKDAYS for d in c.days):
        errs.append("Working days must be names like Mon, Tue, ... Sun.")
    if c.lab_periods < 1:
        errs.append("A lab must be at least 1 period long.")
    for sh in c.shifts:
        if not sh.periods:
            errs.append(f"Shift {sh.name} has no periods.")
        prev_end = None
        for p in sh.periods:
            if not (_time_ok(p.start) and _time_ok(p.end)) or _m(p.end) <= _m(p.start):
                errs.append(f"Shift {sh.name}: period {p.start}-{p.end} isn't a valid time range.")
                break
            if prev_end is not None and _m(p.start) < prev_end:
                errs.append(f"Shift {sh.name}: periods overlap or are out of order at {p.start}.")
                break
            prev_end = _m(p.end)
        if sh.lunch and not (_time_ok(sh.lunch.window_start) and _time_ok(sh.lunch.window_end)):
            errs.append(f"Shift {sh.name}: the mess window isn't a valid time range.")

    depts = {d.id for d in c.departments}
    shifts = {s.id for s in c.shifts}
    sections = {s.id: s for s in c.sections}
    teachers = {t.id for t in c.teachers}
    subjects = {s.id for s in c.subjects}
    for v in c.venues:
        if v.department_id and v.department_id not in depts:
            errs.append(f"Room {v.name} belongs to an unknown department.")
    for s in c.sections:
        if s.department_id not in depts:
            errs.append(f"Section {s.name} belongs to an unknown department.")
        if s.shift_id not in shifts:
            errs.append(f"Section {s.name} uses an unknown shift.")
    for t in c.teachers:
        if t.department_id not in depts:
            errs.append(f"Teacher {t.name} belongs to an unknown department.")
        if any(sh not in shifts for sh in t.shift_ids):
            errs.append(f"Teacher {t.name} uses an unknown shift.")
    for s in c.subjects:
        if s.department_id not in depts:
            errs.append(f"Subject {s.name} belongs to an unknown department.")
    for a in c.allotments:
        if a.subject_id not in subjects:
            errs.append(f"Class {a.id} uses an unknown subject.")
        if a.teacher_id is not None and a.teacher_id not in teachers:
            errs.append(f"Class {a.id} uses an unknown teacher.")
        if any(sid not in sections for sid in a.section_ids):
            errs.append(f"Class {a.id} uses an unknown section.")
        elif a.batch_id and a.batch_id not in {b.id for b in sections[a.section_ids[0]].batches}:
            errs.append(f"Class {a.id} uses a batch that isn't part of its section.")
    for ts in c.teacher_subjects:
        if ts.teacher_id not in teachers or ts.subject_id not in subjects:
            errs.append("A 'can teach' entry refers to an unknown teacher or subject.")
            break
    for st in c.students:
        sec = sections.get(st.section_id)
        if sec is None:
            errs.append(f"Student {st.roll_no} is in an unknown section.")
        elif st.batch_id and st.batch_id not in {b.id for b in sec.batches}:
            errs.append(f"Student {st.roll_no} is in a batch that isn't part of {sec.name}.")
    for slot in c.elective_slots:
        if any(sid not in sections for sid in slot.section_ids):
            errs.append(f"Elective slot {slot.name} uses an unknown section.")
        for g in slot.groups:
            if g.subject_id not in subjects or g.teacher_id not in teachers:
                errs.append(f"Elective group {g.name} uses an unknown subject or teacher.")
    return errs


def apply_settings(college: College, s: Settings) -> tuple[College | None, list[str]]:
    new = college.model_copy(update={
        "days": [d for d in WEEKDAYS if d in s.days], "lab_periods": s.lab_periods, "shifts": s.shifts,
        "holidays": sorted(s.holidays, key=lambda h: h.date), "semester_start": s.semester_start,
        "semester_end": s.semester_end,
    })
    errs = structural_errors(new)
    return (None, errs) if errs else (new, [])


def merge_dept(college: College, dept: str, data: DeptData, actor: str) -> tuple[College | None, list[str]]:
    """Replace one department's slice. Combined classes with other departments stay untouched."""
    errs = []
    for kind, items in (("section", data.sections), ("teacher", data.teachers), ("subject", data.subjects),
                        ("room", data.venues)):
        for it in items:
            if getattr(it, "department_id", dept) != dept:
                errs.append(f"{kind.capitalize()} {getattr(it, 'name', it.id)} belongs to another department.")
    secs = {s.id for s in data.sections}
    for a in data.allotments:
        if not set(a.section_ids) <= secs:
            errs.append(f"Class {a.id} includes another department's section; the College Admin manages those.")
    mine_teachers = {t.id for t in data.teachers}
    if any(ts.teacher_id not in mine_teachers for ts in data.teacher_subjects):
        errs.append("'Can teach' entries must be for this department's teachers.")
    if any(st.section_id not in secs for st in data.students):
        errs.append("Every student must be in one of this department's sections.")
    if errs:
        return None, errs

    old = dept_slice(college, dept)
    old_secs = {s.id for s in old.sections}
    old_ids = {
        "sections": old_secs, "teachers": {t.id for t in old.teachers}, "subjects": {s.id for s in old.subjects},
        "venues": {v.id for v in old.venues}, "allotments": {a.id for a in old.allotments},
    }
    status = dict(college.department_status)
    status[dept] = DepartmentStatus(ready=False, at=time.time(), by=actor)  # changed data: mark Ready again
    new = college.model_copy(update={
        "sections": [s for s in college.sections if s.id not in old_ids["sections"]] + data.sections,
        "teachers": [t for t in college.teachers if t.id not in old_ids["teachers"]] + data.teachers,
        "subjects": [s for s in college.subjects if s.id not in old_ids["subjects"]] + data.subjects,
        "venues": [v for v in college.venues if v.id not in old_ids["venues"]] + data.venues,
        "allotments": [a for a in college.allotments if a.id not in old_ids["allotments"]] + data.allotments,
        "teacher_subjects": [ts for ts in college.teacher_subjects if ts.teacher_id not in old_ids["teachers"]]
        + data.teacher_subjects,
        "students": [st for st in college.students if st.section_id not in old_secs] + data.students,
        "department_status": status,
    })
    errs = structural_errors(new)
    return (None, errs) if errs else (new, [])


def set_ready(college: College, dept: str, ready: bool, actor: str) -> College:
    status = dict(college.department_status)
    status[dept] = DepartmentStatus(ready=ready, at=time.time(), by=actor)
    return college.model_copy(update={"department_status": status})
