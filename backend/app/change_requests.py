"""Teachers' requests to move one of their lectures permanently (root CLAUDE.md §4: teacher requests,
Department Coordinator approves). Only the request is stored here; the move itself goes through the
usual repair -> validate -> preview -> apply path when the Coordinator reviews it."""

from __future__ import annotations

import time

from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import ChangeRequestRow, SessionLocal


class ChangeRequestOut(BaseModel):
    id: str
    at: float
    teacher_name: str
    teacher_id: str
    session_id: str
    day: str
    start_period: int
    summary: str
    reason: str
    status: str
    decided_by: str
    decided_at: float | None
    note: str


def _out(r: ChangeRequestRow) -> ChangeRequestOut:
    return ChangeRequestOut(id=r.id, at=r.at, teacher_name=r.teacher_name, teacher_id=r.teacher_id,
                            session_id=r.session_id, day=r.day, start_period=r.start_period, summary=r.summary,
                            reason=r.reason, status=r.status, decided_by=r.decided_by, decided_at=r.decided_at,
                            note=r.note)


def create(org: str, user_id: str, teacher_name: str, teacher_id: str, department_ids: list[str], session_id: str,
           day: str, start_period: int, summary: str, reason: str) -> ChangeRequestOut:
    with SessionLocal() as db:
        # One open request per class: a new one replaces the old.
        for old in db.scalars(select(ChangeRequestRow).where(
                ChangeRequestRow.org_id == org, ChangeRequestRow.session_id == session_id,
                ChangeRequestRow.status == "pending")):
            old.status, old.decided_at, old.note = "withdrawn", time.time(), "Replaced by a newer request."
        row = ChangeRequestRow(org_id=org, at=time.time(), user_id=user_id, teacher_name=teacher_name,
                               teacher_id=teacher_id, department_ids=department_ids, session_id=session_id, day=day,
                               start_period=start_period, summary=summary, reason=reason)
        db.add(row)
        db.commit()
        return _out(row)


def get(org: str, request_id: str) -> ChangeRequestRow | None:
    with SessionLocal() as db:
        row = db.get(ChangeRequestRow, request_id)
        return row if row is not None and row.org_id == org else None


def listing(org: str, *, teacher_id: str | None = None, department_id: str | None = None) -> list[ChangeRequestOut]:
    """Pending first, newest first. Filter by the requesting teacher or a Coordinator's department."""
    with SessionLocal() as db:
        rows = db.scalars(select(ChangeRequestRow).where(ChangeRequestRow.org_id == org)
                          .order_by(ChangeRequestRow.at.desc()).limit(200)).all()
    if teacher_id is not None:
        rows = [r for r in rows if r.teacher_id == teacher_id]
    if department_id is not None:
        rows = [r for r in rows if department_id in r.department_ids]
    return [_out(r) for r in sorted(rows, key=lambda r: r.status != "pending")]


def decide(org: str, request_id: str, status: str, by: str, note: str = "") -> ChangeRequestOut | None:
    with SessionLocal() as db:
        row = db.get(ChangeRequestRow, request_id)
        if row is None or row.org_id != org or row.status != "pending":
            return None
        row.status, row.decided_by, row.decided_at, row.note = status, by, time.time(), note[:500]
        db.commit()
        return _out(row)


def pending_count(org: str, department_id: str | None) -> int:
    return sum(1 for r in listing(org, department_id=department_id) if r.status == "pending")
