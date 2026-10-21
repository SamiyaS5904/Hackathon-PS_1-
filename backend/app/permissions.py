"""Who may do what (root CLAUDE.md §4). Every endpoint calls one of these; each is unit-tested.

Functions return "" when allowed, or a plain-language reason when not.
"""

from __future__ import annotations

from app.accounts import Member
from app.models.domain import College, Session, Timetable

STAFF = ("admin", "coordinator")


def _session_departments(college: College, s: Session) -> set[str]:
    return {college.section(i).department_id for i in s.section_ids}


def can_generate(m: Member) -> str:
    return "" if m.role == "admin" else "Only the College Admin can generate the timetable."


def can_edit_weekly(m: Member, college: College, s: Session) -> str:
    """Permanent (weekly plan) changes."""
    if m.role == "admin":
        return ""
    if m.role == "coordinator":
        if _session_departments(college, s) <= {m.department_id}:
            return ""
        return "This class involves another department, so only the College Admin can change it."
    if m.role == "teacher":
        if s.teacher_id != m.teacher_id:
            return "You can only change your own lectures."
        return "Permanent changes to the weekly plan need your Department Coordinator's approval."
    return "Students can't change the timetable."


def can_edit_one_day(m: Member, college: College, s: Session) -> str:
    """One-day changes: teachers may change their own lectures instantly."""
    if m.role == "teacher":
        return "" if s.teacher_id == m.teacher_id else "You can only change your own lectures."
    if m.role in STAFF:
        return can_edit_weekly(m, college, s)
    return "Students can't change the timetable."


def can_view_activity(m: Member) -> str:
    return "" if m.role in STAFF else "Only the College Admin and Department Coordinators can see the change history."


def can_undo(m: Member, actor_name: str) -> str:
    if m.role == "admin":
        return ""
    if m.role == "coordinator":
        return "" if actor_name == m.name else "You can only undo changes you made."
    return "Only the College Admin and Department Coordinators can undo changes."


def can_invite(m: Member, role: str, department_id: str | None) -> str:
    if m.role == "admin":
        return "" if role in ("admin", "coordinator", "teacher") else "Students join with their college email."
    if m.role == "coordinator":
        if role == "teacher" and department_id == m.department_id:
            return ""
        return "Coordinators can invite teachers of their own department."
    return "You can't invite people to this college."


def can_manage_college(m: Member) -> str:
    return "" if m.role == "admin" else "Only the College Admin can change college settings."


def visible_sessions(m: Member, college: College, tt: Timetable) -> list[Session]:
    """What each role may see: staff everything; teachers their own + their department; students their section."""
    if m.role in STAFF:
        return tt.sessions
    if m.role == "teacher":
        return [s for s in tt.sessions
                if s.teacher_id == m.teacher_id or m.department_id in _session_departments(college, s)]
    if m.role == "student":
        return [s for s in tt.sessions
                if m.section_id in s.section_ids and (s.batch_id is None or s.batch_id == m.batch_id)]
    return []


def college_for(m: Member, college: College) -> College:
    """Students and teachers never receive other students' personal details."""
    if m.role in STAFF:
        return college
    own = [s for s in college.students if m.role == "student" and s.section_id == m.section_id
           and s.email == m.email]
    return college.model_copy(update={"students": own})
