"""Notices: short messages from a Department Coordinator or the College Admin, shown on Home until they expire.

Audience (one of):
- ``college``: everyone (College Admin only)
- ``dept_teachers``: the department's teachers (and its Coordinator)
- ``dept_students``: every student of the department
- ``year``: the department's students of one year
- ``section``: one section's students

A Coordinator posts to their own department only; the College Admin to any department or the whole
college. Posting also rings the bell for the same people (app/notify.py). Notices live in memory (loaded
per college on first use) and are saved by the background writer, in their own table.
"""

from __future__ import annotations

import threading
import time

from pydantic import BaseModel, Field
from sqlalchemy import JSON, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from app.accounts import Member
from app.db.models import Base, SessionLocal, new_id
from app.models.domain import College
from app.notify import Audience, matches
from app.store import writer

KINDS = ("college", "dept_teachers", "dept_students", "year", "section")


class NoticeRow(Base):
    """One notice; the fields live in ``data`` (see ``Notice``)."""

    __tablename__ = "notices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class Notice(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    body: str = ""
    kind: str  # one of KINDS
    department_id: str | None = None
    year: int | None = None
    section_id: str | None = None
    expires: str  # YYYY-MM-DD, last day it is shown
    audience: Audience
    for_whom: str  # "CSE students, year 3"
    created_by: str  # user id
    created_by_name: str
    created_at: float = Field(default_factory=time.time)


class NoticeOut(Notice):
    can_delete: bool = False


_lock = threading.Lock()
_notices: dict[str, dict[str, Notice]] = {}  # org -> id -> notice


def _load(org: str) -> dict[str, Notice]:
    with _lock:
        if org in _notices:
            return _notices[org]
    with SessionLocal() as db:
        rows = db.scalars(select(NoticeRow).where(NoticeRow.org_id == org)).all()
    items = {r.id: Notice(**r.data) for r in rows}
    with _lock:
        return _notices.setdefault(org, items)


def audience_for(college: College, kind: str, dept: str | None, year: int | None,
                 section_id: str | None) -> tuple[Audience | None, str]:
    """Who the notice reaches, and a short label, or (None, reason) when the choice doesn't make sense."""
    short = next((d.short for d in college.departments if d.id == dept), None)
    if kind == "college":
        return Audience(everyone=True), "Everyone"
    if short is None:
        return None, "Choose a department."
    if kind == "dept_teachers":
        return Audience(teacher_ids=[t.id for t in college.teachers if t.department_id == dept],
                        coordinator_departments=[dept]), f"{short} teachers"
    secs = [s for s in college.sections if s.department_id == dept]
    if kind == "dept_students":
        return Audience(section_ids=[s.id for s in secs]), f"{short} students"
    if kind == "year":
        chosen = [s.id for s in secs if s.year == year]
        if not chosen:
            return None, f"{short} has no sections in year {year}."
        return Audience(section_ids=chosen), f"{short} students, year {year}"
    if kind == "section":
        sec = next((s for s in secs if s.id == section_id), None)
        if sec is None:
            return None, "Choose a section of the department."
        return Audience(section_ids=[sec.id]), f"{sec.name} students"
    return None, "Unknown audience."


def can_post(m: Member, kind: str, dept: str | None) -> str:
    if m.role == "admin":
        return ""
    if m.role == "coordinator":
        if kind == "college":
            return "Only the College Admin posts notices to the whole college."
        return "" if dept == m.department_id else "Coordinators post notices to their own department."
    return "Notices are posted by the Department Coordinator or the College Admin."


def post(college: College, org: str, m: Member, title: str, body: str, kind: str, dept: str | None,
         year: int | None, section_id: str | None, expires: str, today: str) -> tuple[Notice | None, str]:
    if kind not in KINDS:
        return None, "Unknown audience."
    why = can_post(m, kind, dept)
    if why:
        return None, why
    if not title.strip():
        return None, "Write the notice."
    if expires < today:
        return None, "The last day to show it can't be in the past."
    audience, label = audience_for(college, kind, None if kind == "college" else dept, year, section_id)
    if audience is None:
        return None, label
    n = Notice(title=title.strip()[:160], body=body.strip()[:1000], kind=kind,
               department_id=None if kind == "college" else dept, year=year if kind == "year" else None,
               section_id=section_id if kind == "section" else None, expires=expires, audience=audience,
               for_whom=label, created_by=m.user_id, created_by_name=m.name)
    items = _load(org)
    with _lock:
        items[n.id] = n
    data = n.model_dump()
    writer.submit(lambda db: db.add(NoticeRow(id=n.id, org_id=org, data=data)))
    return n, f"Posted for {label} until {expires}."


def remove(org: str, m: Member, notice_id: str) -> Notice | None:
    items = _load(org)
    n = items.get(notice_id)
    if n is None or not (n.created_by == m.user_id or m.role == "admin"):
        return None
    with _lock:
        items.pop(notice_id, None)

    def rm(db) -> None:
        row = db.get(NoticeRow, notice_id)
        if row is not None:
            db.delete(row)

    writer.submit(rm)
    return n


def visible(org: str, m: Member, today: str) -> list[NoticeOut]:
    """Notices still showing that are meant for this member (plus the ones they posted), newest first."""
    out = []
    for n in _load(org).values():
        if n.expires < today:
            continue
        mine = n.created_by == m.user_id
        staff_view = m.role == "admin" or (m.role == "coordinator" and n.department_id == m.department_id)
        if mine or staff_view or matches(n.audience, m):
            out.append(NoticeOut(**n.model_dump(), can_delete=mine or m.role == "admin"))
    return sorted(out, key=lambda n: -n.created_at)
