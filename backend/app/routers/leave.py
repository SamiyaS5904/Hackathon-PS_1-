"""Teacher leave: ask / approve, the cover plan (preview) and applying it.

Permissions (root CLAUDE.md §4): a teacher asks for their own leave; the Department Coordinator approves and
plans cover for their own department's teachers; the College Admin for anyone. The plan is a read-only
preview; applying it is the person's own click and goes validator -> apply -> activity log -> notifications.
"""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import leave
from app.core.deps import Ctx, allow, org_ctx
from app.edits.oneday import label
from app.leave import CoverChoice, LeaveOut, LeavePlan
from app.models.domain import Teacher
from app.notify import Audience, notify_change, send
from app.store import store

router = APIRouter(prefix="/api/orgs/{org}/leaves", tags=["leave"])

DATE = r"^\d{4}-\d{2}-\d{2}$"


def _teacher(ctx: Ctx, teacher_id: str | None) -> Teacher:
    """The teacher this member may handle leave for: themself (teacher), own department (Coordinator), anyone (Admin)."""
    m = ctx.member
    if m.role == "student":
        raise HTTPException(403, "Students can't handle teacher leave.")
    if m.role == "teacher":
        if not m.teacher_id or (teacher_id and teacher_id != m.teacher_id):
            raise HTTPException(403, "You can only ask for your own leave.")
        teacher_id = m.teacher_id
    t = next((x for x in ctx.state.college.teachers if x.id == teacher_id), None)
    if t is None:
        raise HTTPException(404, "Teacher not found.")
    if m.role == "coordinator" and t.department_id != m.department_id:
        raise HTTPException(403, "You can handle leave for your own department's teachers.")
    return t


def _editable(ctx: Ctx):
    tt = ctx.state.timetable
    if tt is None or not tt.sessions:
        raise HTTPException(404, "No timetable generated yet")
    if not ctx.live:
        raise HTTPException(409, "The College Admin is preparing an updated timetable. Changes open again once it "
                                 "is published.")
    if tt.college_revision != ctx.state.college.revision:
        raise HTTPException(409, "The college data changed since this timetable was generated. Ask the College "
                                 "Admin to regenerate it first.")
    return tt


def _dates(ctx: Ctx, start: str, end: str) -> list[str]:
    try:
        return leave.working_dates(ctx.state.college, start, end)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


def _when(start: str, end: str) -> str:
    return label(start) if start == end else f"{label(start)} to {label(end)}"


@router.get("", response_model=list[LeaveOut])
def list_leaves(ctx: Ctx = Depends(org_ctx)) -> list[LeaveOut]:
    m = ctx.member
    if m.role == "teacher":
        return leave.listing(ctx.state.id, teacher_id=m.teacher_id or "-")
    allow("" if m.role in ("admin", "coordinator") else "Students can't see teacher leave.")
    return leave.listing(ctx.state.id, department_id=m.department_id if m.role == "coordinator" else None)


class LeaveRequest(BaseModel):
    teacher_id: str | None = None  # staff: whose leave; teachers: left out (their own)
    start_date: str = Field(pattern=DATE)
    end_date: str = Field(pattern=DATE)
    reason: str = Field(default="", max_length=500)


@router.post("", response_model=LeaveOut, status_code=201)
def create_leave(body: LeaveRequest, ctx: Ctx = Depends(org_ctx)) -> LeaveOut:
    """A teacher asks (waits for the Coordinator); staff enter it directly (approved)."""
    t = _teacher(ctx, body.teacher_id)
    _dates(ctx, body.start_date, body.end_date)
    asking = ctx.member.role == "teacher"
    out = leave.create(ctx.state.id, t.id, t.name, t.department_id, body.start_date, body.end_date, body.reason,
                       requested_by=ctx.user.name, status="pending" if asking else "approved",
                       decided_by="" if asking else ctx.user.name)
    when = _when(body.start_date, body.end_date)
    if asking:
        send(ctx.state.id, f"{t.name} asks for leave: {when}", body.reason or "Open Home to approve and plan cover.",
             Audience(coordinator_departments=[t.department_id], roles=["admin"]), ctx.user.id, link="/")
    return out


class Decision(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=500)


@router.post("/{leave_id}/decide", response_model=LeaveOut)
def decide_leave(leave_id: str, body: Decision, ctx: Ctx = Depends(org_ctx)) -> LeaveOut:
    allow("" if ctx.member.role in ("admin", "coordinator") else "Leave is approved by the Coordinator.")
    lv = leave.get(ctx.state.id, leave_id)
    if lv is None:
        raise HTTPException(404, "Leave not found.")
    _teacher(ctx, lv.teacher_id)
    if lv.status != "pending":
        raise HTTPException(409, "This leave was already decided.")
    out = leave.update(ctx.state.id, leave_id, status="approved" if body.approve else "declined",
                       decided_by=ctx.user.name, decided_at=time.time(), note=body.note)
    word = "approved" if body.approve else "declined"
    send(ctx.state.id, f"Your leave {_when(lv.start_date, lv.end_date)} is {word}",
         body.note or ("Your classes will be covered; you'll see the plan once it's applied." if body.approve else ""),
         Audience(teacher_ids=[lv.teacher_id]), ctx.user.id, link="/")
    return out


class PlanRequest(BaseModel):
    teacher_id: str
    start_date: str = Field(pattern=DATE)
    end_date: str = Field(pattern=DATE)
    actions: dict[int, Literal["substitute", "cancel"]] = Field(default_factory=dict)  # per year
    default: Literal["substitute", "cancel"] = "substitute"


@router.post("/plan", response_model=LeavePlan)
def plan_leave(body: PlanRequest, ctx: Ctx = Depends(org_ctx)) -> LeavePlan:
    """Preview only: nothing is saved."""
    allow("" if ctx.member.role in ("admin", "coordinator") else "Cover is planned by the Coordinator.")
    t = _teacher(ctx, body.teacher_id)
    tt = _editable(ctx)
    _dates(ctx, body.start_date, body.end_date)
    return leave.build_plan(ctx.state.college, tt, t.id, body.start_date, body.end_date, body.actions, body.default)


class ApplyRequest(BaseModel):
    leave_id: str | None = None  # an asked-for leave; left out = a new leave entered by staff
    teacher_id: str
    start_date: str = Field(pattern=DATE)
    end_date: str = Field(pattern=DATE)
    reason: str = Field(default="", max_length=500)
    choices: list[CoverChoice] = Field(default_factory=list, max_length=120)
    via: Literal["app", "chatbot"] = "app"  # only labels the activity log


class ApplyOut(BaseModel):
    message: str
    leave: LeaveOut
    entry_id: str | None = None  # activity entry, for Undo


@router.post("/apply", response_model=ApplyOut, status_code=201)
def apply_leave(body: ApplyRequest, ctx: Ctx = Depends(org_ctx)) -> ApplyOut:
    allow("" if ctx.member.role in ("admin", "coordinator") else "Cover is planned by the Coordinator.")
    t = _teacher(ctx, body.teacher_id)
    tt = _editable(ctx)
    _dates(ctx, body.start_date, body.end_date)
    lv = leave.get(ctx.state.id, body.leave_id) if body.leave_id else None
    if body.leave_id and (lv is None or lv.teacher_id != t.id):
        raise HTTPException(404, "Leave not found.")
    if lv is not None and lv.status in ("declined", "withdrawn"):
        raise HTTPException(409, "This leave was declined.")
    if lv is not None and lv.applied_at:
        raise HTTPException(409, "Cover for this leave is already in place. Undo it from Changes to plan again.")
    in_range = all(body.start_date <= c.date <= body.end_date for c in body.choices)
    if not in_range:
        raise HTTPException(422, "Every class in the plan must fall on the days of the leave.")
    reason = body.reason or (lv.reason if lv else "")
    entry_id = None
    covered = sum(1 for c in body.choices if c.action == "substitute")
    summary = f"{covered} covered, {len(body.choices) - covered} cancelled" if body.choices else "no classes to cover"
    title = f"{t.name} on leave {_when(body.start_date, body.end_date)}: {summary}"
    if body.choices:
        new, error, _ = leave.apply_plan(ctx.state.college, tt, t.id, body.choices, reason, ctx.user.name)
        if new is None:
            raise HTTPException(422, error + " Nothing was changed.")
        entry = store.set_timetable(ctx.state.id, new, action=title,
                                    source="chatbot" if body.via == "chatbot" else "one-day", actor=ctx.user.name)
        entry_id = entry.id
        notify_change(ctx.state.id, ctx.state.college, tt, new, title,
                      "Some classes have a substitute teacher and some are cancelled for those days. "
                      "Open your timetable to see yours.", ctx.user.id)
        if new.published_at:
            for sub_id in sorted({c.teacher_id for c in body.choices if c.action == "substitute" and c.teacher_id}):
                mine = [c for c in body.choices if c.teacher_id == sub_id]
                lines = []
                for c in mine:
                    s = next(x for x in tt.sessions if x.id == c.session_id)
                    lines.append(f"{ctx.state.college.subject(s.subject_id).name} {label(c.date)} {s.start}")
                send(ctx.state.id, f"You're covering {len(mine)} class{'es' if len(mine) != 1 else ''} for {t.name}",
                     "; ".join(lines), Audience(teacher_ids=[sub_id]), ctx.user.id)
    if lv is None:
        lv = leave.create(ctx.state.id, t.id, t.name, t.department_id, body.start_date, body.end_date, reason,
                          requested_by=ctx.user.name, status="approved", decided_by=ctx.user.name)
    lv = leave.update(ctx.state.id, lv.id, status="approved", applied_at=time.time(), plan_summary=summary,
                      decided_by=lv.decided_by or ctx.user.name)
    return ApplyOut(message=f"Done. {title}. Everyone affected is told." if body.choices else
                    f"Leave saved. {t.name} has no classes on those days.", leave=lv, entry_id=entry_id)
