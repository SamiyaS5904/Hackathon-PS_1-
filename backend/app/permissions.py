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


def can_request_move(m: Member, s: Session) -> str:
    """Teachers ask their Department Coordinator for a permanent move of their own lecture."""
    if m.role != "teacher":
        return "Only teachers send change requests; you can move classes directly."
    if s.teacher_id != m.teacher_id:
        return "You can only ask to move your own lectures."
    if s.elective_slot_id:
        return "Elective slots move together for every group; ask the College Admin."
    return ""


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
    """What each role may see: staff everything; teachers only their own lectures; students their own classes."""
    if m.role in STAFF:
        return tt.sessions
    if m.role == "teacher":
        return [s for s in tt.sessions if s.teacher_id == m.teacher_id]
    if m.role == "student":
        me = next((st.id for st in college.students if st.email == m.email), None)
        out = []
        for s in tt.sessions:
            if s.elective_slot_id:
                if me and me in college.elective_group(s.elective_slot_id, s.group_id).student_ids:
                    out.append(s)
            elif m.section_id in s.section_ids and (s.batch_id is None or s.batch_id == m.batch_id):
                out.append(s)
        return out
    return []


def college_for(m: Member, college: College) -> College:
    """Students and teachers never receive other students' personal details."""
    if m.role in STAFF:
        return college
    own = [s for s in college.students if m.role == "student" and s.section_id == m.section_id
           and s.email == m.email]
    return college.model_copy(update={"students": own})
