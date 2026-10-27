"""Timetabl.ai backend API.

Every /api/orgs/{org}/... endpoint requires a logged-in member of that college,
and every action checks the role rules in app/permissions.py.
"""

from __future__ import annotations

import datetime
import re
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import accounts
from app.accounts import InviteOut, Member
from app.assist import Explanation, FreeRoom, Insight, TeacherNow, explain, free_rooms, insights, teacher_now
from app.college_edit import (
    DeptData,
    Settings,
    apply_settings,
    dept_slice,
    merge_dept,
    set_ready,
    settings_of,
    structural_errors,
)
from app.core.config import AUTO_DEMO_TIMETABLE, CORS_ORIGIN_REGEX, CORS_ORIGINS
from app.core.deps import Ctx, allow, current_user, org_ctx
from app.core.security import create_token
from app.db.models import UserRow
from app.edits import regenerate
from app.edits.moves import Change, MoveOption, diff, move_options, repair_move
from app.edits.oneday import (DayInfo, MakeupOption, Occurrence, add_override, day_options, label, makeup_options,
                              occurrences, remove_override, week)
from app.edits.oneday import _day as one_day
from app.io.excel import RowError
from app.io.excel import mark_errors
from app.io.excel import parse as excel_parse
from app.io.excel import template as excel_template
from app.io.export import build_grid, entity_name, to_pdf, to_xlsx
from app import attendance, change_requests, platform, sectioning
from app.routers.bookings import router as bookings_router
from app.routers.platform import router as platform_router
from app.routers.assistant_proxy import router as assistant_proxy_router
from app.routers.demo import router as demo_router
from app.routers.leave import router as leave_router
from app.routers.usage import router as usage_router
from app.routers.today import router as today_router
from app.today import Problem, locate
from app.change_requests import ChangeRequestOut
from app.notify import Audience, FeedOut, feed, mark_seen, notify_change, send
from app.notify import warm as notify_warm
from app.models.domain import College, Department, DepartmentStatus, Rule, TimeBlock, Timetable, Venue
from app.permissions import (
    can_edit_one_day,
    can_edit_weekly,
    can_generate,
    can_invite,
    can_manage_college,
    can_request_move,
    can_undo,
    can_view_activity,
    college_for,
    visible_sessions,
)
from app.seed.demo_college import build_demo_college, empty_college
from app.solver.allotment import SuggestResult, suggest
from app.solver.feasibility import check, warnings
from app.solver.generate import generate
from app.solver.quality import QualityReport, score
from app.store import store, writer
from app.validator.check import Violation, validate


def ensure_demo_timetable(org_id: str = "demo", time_limit: float = 45) -> None:
    """A demo college always shows a current, published timetable: when it has none (first start, e.g. a new
    deployment) or its data changed, build and publish one in the background."""
    demo = store.org(org_id)
    if demo is None or not AUTO_DEMO_TIMETABLE:
        return
    tt = demo.timetable
    if tt is not None and tt.sessions and tt.college_revision == demo.college.revision and tt.published_at:
        return

    def run() -> None:
        new = generate(demo.college, time_limit=time_limit)
        new.college_revision = demo.college.revision
        if not new.sessions:
            return
        store.set_timetable(org_id, new, action=f"Generated timetable ({len(new.sessions)} classes)",
                            source="generate", actor="System")
        store.publish(org_id, "System")

    threading.Thread(target=run, name=f"{org_id}-timetable", daemon=True).start()


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.load()
    accounts.seed_demo()
    ensure_demo_timetable()
    ensure_demo_timetable("gndec", time_limit=180)  # bigger college: more time for fewer gaps (once)
    notify_warm(store.org_ids())
    yield
    writer.flush()  # nothing queued is lost on shutdown


app = FastAPI(title="Timetabl.ai API", version="0.4.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_origin_regex=CORS_ORIGIN_REGEX,
                   allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Content-Disposition"])  # file names for downloads
app.include_router(bookings_router)
app.include_router(platform_router)
app.include_router(today_router)
app.include_router(leave_router)
app.include_router(assistant_proxy_router)
app.include_router(demo_router)
app.include_router(usage_router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------------------
# Accounts: signup, login, me, invites, members
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    college_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthOut(BaseModel):
    token: str
    user_id: str
    name: str
    email: str
    memberships: list[Member]
    platform_owner: bool = False  # Super Admin: sees the platform page (every college's health)


class InviteRequest(BaseModel):
    email: str
    role: str
    department_id: str | None = None
    teacher_id: str | None = None


class AcceptRequest(BaseModel):
    name: str = ""
    password: str


def _auth_out(user: UserRow) -> AuthOut:
    return AuthOut(token=create_token(user.id), user_id=user.id, name=user.name, email=user.email,
                   memberships=accounts.memberships(user.id), platform_owner=platform.is_owner(user))


@app.post("/api/auth/signup", response_model=AuthOut, status_code=201)
def signup(body: SignupRequest) -> AuthOut:
    email = accounts.normalize_email(body.email)
    if not accounts.valid_email(email):
        raise HTTPException(422, "Enter a valid email address.")
    if len(body.password) < 8:
        raise HTTPException(422, "Choose a password with at least 8 characters.")
    if not body.name.strip() or not body.college_name.strip():
        raise HTTPException(422, "Enter your name and your college's name.")
    if accounts.find_user(email):
        raise HTTPException(409, "An account with this email already exists. Log in instead.")
    user = accounts.create_user(email, body.name, body.password)
    org = store.create_org(body.college_name.strip(), empty_college(body.college_name.strip()))
    accounts.add_membership(user.id, org.id, "admin")
    return _auth_out(user)


@app.post("/api/auth/login", response_model=AuthOut)
def login(body: LoginRequest) -> AuthOut:
    user = accounts.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(401, "Wrong email or password.")
    return _auth_out(user)


@app.get("/api/me", response_model=AuthOut)
def me(user: UserRow = Depends(current_user)) -> AuthOut:
    return _auth_out(user)


@app.get("/api/invites/{token}", response_model=InviteOut)
def read_invite(token: str) -> InviteOut:
    inv = accounts.get_invite(token)
    if inv is None or inv.status != "pending":
        raise HTTPException(404, "This invite link is no longer valid.")
    return inv


@app.post("/api/invites/{token}/accept", response_model=AuthOut)
def accept(token: str, body: AcceptRequest) -> AuthOut:
    user, error = accounts.accept_invite(token, body.name, body.password)
    if user is None:
        raise HTTPException(422, error)
    return _auth_out(user)


@app.get("/api/orgs/{org}/members", response_model=list[Member])
def members(ctx: Ctx = Depends(org_ctx)) -> list[Member]:
    allow("" if ctx.member.role in ("admin", "coordinator") else "Only staff can see the member list.")
    return accounts.list_members(ctx.state.id)


@app.get("/api/orgs/{org}/invites", response_model=list[InviteOut])
def invites(ctx: Ctx = Depends(org_ctx)) -> list[InviteOut]:
    allow("" if ctx.member.role in ("admin", "coordinator") else "Only staff can see invites.")
    return accounts.list_invites(ctx.state.id)


@app.post("/api/orgs/{org}/invites", response_model=InviteOut, status_code=201)
def invite(body: InviteRequest, ctx: Ctx = Depends(org_ctx)) -> InviteOut:
    allow(can_invite(ctx.member, body.role, body.department_id))
    email = accounts.normalize_email(body.email)
    if not accounts.valid_email(email):
        raise HTTPException(422, "Enter a valid email address.")
    college = ctx.state.college
    if body.department_id and body.department_id not in {d.id for d in college.departments}:
        raise HTTPException(422, "Unknown department.")
    if body.teacher_id and body.teacher_id not in {t.id for t in college.teachers}:
        raise HTTPException(422, "Unknown teacher.")
    if body.role in ("coordinator", "teacher") and not body.department_id:
        raise HTTPException(422, "Choose the department.")
    return accounts.create_invite(ctx.state.id, email, body.role, ctx.user.name, body.department_id, body.teacher_id)


# ---------------------------------------------------------------------------
# College data, generation, timetable
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    time_limit: float = 45.0
    # Mid-semester: keep the current timetable as much as possible (only classes that must move do).
    keep_current: bool = False


class JobOut(BaseModel):
    id: str
    status: str
    elapsed: float
    error: str | None = None
    message: str = ""


class LastChange(BaseModel):
    id: str  # audit entry id: Undo targets exactly this change
    at: float
    actor: str
    action: str
    can_undo: bool


class TimetableOut(BaseModel):
    timetable: Timetable
    quality: QualityReport | None
    violations: list[Violation]
    stale: bool = False  # college data changed since this timetable was generated
    ever_published: bool = False  # teachers and students can see a timetable
    last_change: LastChange | None = None  # staff only: who changed the timetable last, and when


class PrecheckOut(BaseModel):
    problems: list[str]
    warnings: list[str]
    located: list[Problem] = []  # the same problems, each with the page where it can be fixed


class OrgOut(BaseModel):
    id: str
    name: str
    is_demo: bool
    role: str
    student_accounts: int


@app.get("/api/orgs/{org}", response_model=OrgOut)
def get_org(ctx: Ctx = Depends(org_ctx)) -> OrgOut:
    return OrgOut(id=ctx.state.id, name=ctx.state.name, is_demo=ctx.state.is_demo, role=ctx.member.role,
                  student_accounts=accounts.count_students(ctx.state.id) if ctx.member.role == "admin" else 0)


@app.get("/api/orgs/{org}/college", response_model=College)
def get_college(ctx: Ctx = Depends(org_ctx)) -> College:
    return college_for(ctx.member, ctx.state.college)


@app.post("/api/orgs/{org}/load-sample", response_model=College)
def load_sample(ctx: Ctx = Depends(org_ctx)) -> College:
    """Fill a new college with the sample data (departments, rooms, sections, teachers, subjects)."""
    allow(can_manage_college(ctx.member))
    if ctx.state.college.allotments or ctx.state.college.departments:
        raise HTTPException(409, "This college already has its own departments; the sample is only for a new college.")
    sample = build_demo_college().model_copy(update={"id": ctx.state.id, "name": ctx.state.name})
    # Keep the sample's structure and electives, but this college's own students come from its list.
    sample.students = [st.model_copy(update={"email": st.email.replace("@demo.timetabl.ai", f"@{ctx.state.id}.edu")})
                       for st in sample.students]
    # The sample's departments are complete, so they arrive Ready and the admin can generate straight away.
    sample.department_status = {d.id: DepartmentStatus(ready=True, at=time.time(), by="Sample data")
                                for d in sample.departments}
    return store.update_college(ctx.state.id, sample)


@app.get("/api/orgs/{org}/precheck", response_model=PrecheckOut)
def precheck(ctx: Ctx = Depends(org_ctx)) -> PrecheckOut:
    college = ctx.state.college
    problems = check(college)
    return PrecheckOut(problems=problems, warnings=warnings(college), located=[locate(college, p) for p in problems])


@app.post("/api/orgs/{org}/timetable/generate", response_model=JobOut, status_code=202)
def start_generation(body: GenerateRequest, ctx: Ctx = Depends(org_ctx)) -> JobOut:
    allow(can_generate(ctx.member))
    org, college, actor = ctx.state.id, ctx.state.college, ctx.user.name
    allow("" if not check(college) else "Fix the data problems shown on the dashboard first.")
    if store.running_job(org):
        raise HTTPException(409, "A timetable is already being generated for this college.")
    job = store.new_job(org)

    old = ctx.state.timetable if body.keep_current else None

    def run() -> None:
        try:
            limit = max(5.0, min(body.time_limit, 300.0))
            if old is not None and old.sessions:
                tt = generate(college, time_limit=limit, keep=regenerate.keep_map(old))
                if tt.sessions:
                    tt, summary = regenerate.finish(college, old, tt, actor)
                    tt.college_revision = college.revision
                    job.message = summary.sentence()
                    store.set_timetable(org, tt, action=f"Regenerated with minimal change: {job.message}",
                                        source="generate", actor=actor, changes=summary.changes)
            else:
                tt = generate(college, time_limit=limit)
                tt.college_revision = college.revision
                if tt.sessions:
                    store.set_timetable(org, tt, action=f"Generated timetable ({len(tt.sessions)} classes)",
                                        source="generate", actor=actor)
            if not tt.sessions:
                job.error = "; ".join(tt.messages) or "No timetable could be built."
            job.status = "done" if tt.sessions else "failed"
        except Exception as exc:  # surfaced to the UI, never swallowed
            job.status, job.error = "failed", str(exc)
        finally:
            job.finished_at = time.time()

    threading.Thread(target=run, daemon=True).start()
    return JobOut(id=job.id, status=job.status, elapsed=0.0)


@app.get("/api/orgs/{org}/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, ctx: Ctx = Depends(org_ctx)) -> JobOut:
    job = store.job(job_id)
    if job is None or job.org != ctx.state.id:
        raise HTTPException(404, "Job not found")
    end = job.finished_at or time.time()
    return JobOut(id=job.id, status=job.status, elapsed=round(end - job.started_at, 1), error=job.error,
                  message=job.message)


def _timetable_out(ctx: Ctx) -> TimetableOut:
    tt = ctx.state.timetable
    if tt is None:
        raise HTTPException(404, NOT_PUBLISHED if ctx.member.role in ("teacher", "student")
                            else "No timetable generated yet")
    college = ctx.state.college
    stale = tt.college_revision != college.revision
    if stale:  # the data it was built from has changed: don't score it against new data
        quality, violations = None, []
    else:
        quality = score(college, tt.sessions, tt.lunches) if tt.sessions else None
        violations = validate(college, tt.sessions, tt.lunches) if tt.sessions else []
    last = None
    if ctx.member.role not in ("admin", "coordinator"):
        tt = tt.model_copy(update={"sessions": visible_sessions(ctx.member, college, tt)})
    else:
        entry = next((e for e in reversed(store.org(ctx.state.id).audit) if e.source != "publish"), None)
        undoable = store.last_undoable(ctx.state.id)
        if entry is not None:
            last = LastChange(id=entry.id, at=entry.at, actor=entry.actor, action=entry.action,
                              can_undo=undoable is not None and undoable.id == entry.id)
    return TimetableOut(timetable=tt, quality=quality, violations=violations, stale=stale,
                        ever_published=ctx.state.published is not None, last_change=last)


@app.get("/api/orgs/{org}/timetable", response_model=TimetableOut)
def get_timetable(ctx: Ctx = Depends(org_ctx)) -> TimetableOut:
    return _timetable_out(ctx)


@app.get("/api/orgs/{org}/export")
def export_timetable(format: Literal["xlsx", "pdf"] = "xlsx", view: Literal["section", "teacher", "venue"] = "section",
                     id: str | None = None, ctx: Ctx = Depends(org_ctx)) -> Response:
    """Weekly timetable as Excel or PDF. Without ``id``: every section / teacher / room (staff only).
    Teachers and students only ever get classes they can see in the app."""
    state = _current(ctx)
    college, tt = state.college, state.timetable
    role = ctx.member.role
    if id is None:
        allow("" if role in ("admin", "coordinator") else "You can download your own timetable.")
        ids = {"section": [s.id for s in college.sections], "teacher": [t.id for t in college.teachers],
               "venue": [v.id for v in college.venues]}[view]
    else:
        known = {"section": {s.id for s in college.sections}, "teacher": {t.id for t in college.teachers},
                 "venue": {v.id for v in college.venues}}[view]
        if id not in known:
            raise HTTPException(404, "Not found in this college.")
        if role == "student" and (view != "section" or id != ctx.member.section_id):
            raise HTTPException(403, "You can download your own section's timetable.")
        if role == "teacher" and (view != "teacher" or id != ctx.member.teacher_id):
            raise HTTPException(403, "You can download your own timetable.")
        ids = [id]
    sessions = visible_sessions(ctx.member, college, tt)
    if view == "teacher" and id is None:  # skip teachers with nothing to print
        ids = [i for i in ids if any(s.teacher_id == i for s in sessions)]
    grids = [build_grid(college, tt, sessions, view, i) for i in ids]
    name = entity_name(college, view, id) if id else {"section": "all sections", "teacher": "all teachers",
                                                      "venue": "all rooms"}[view]
    filename = re.sub(r"[^A-Za-z0-9]+", "-", f"{college.name} {name}").strip("-") + f".{format}"
    if format == "xlsx":
        body, media = to_xlsx(college, tt, grids), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body, media = to_pdf(college, tt, grids), "application/pdf"
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/orgs/{org}/timetable/publish", response_model=TimetableOut)
def publish_timetable(ctx: Ctx = Depends(org_ctx)) -> TimetableOut:
    """Admin only. Teachers and students see the timetable from now on, and later edits reach them live."""
    allow(can_generate(ctx.member))
    state = _current(ctx, for_edit=True)
    if state.timetable.published_at:
        raise HTTPException(409, "This timetable is already published.")
    if validate(state.college, state.timetable.sessions, state.timetable.lunches):  # golden rule #1
        raise HTTPException(409, "This timetable has clashes, so it can't be published.")
    first = state.published is None
    store.publish(state.id, ctx.user.name)
    send(state.id, "Timetable published" if first else "Timetable updated",
         "Your timetable is ready. Open it to see your classes, rooms and teachers." if first else
         "The College Admin published an updated timetable. Check your classes.",
         Audience(everyone=True), ctx.user.id)
    return _timetable_out(ctx)


# ---------------------------------------------------------------------------
# Editing: move options, proposals with repair, apply, audit, undo
# ---------------------------------------------------------------------------

class ProposalRequest(BaseModel):
    session_id: str
    day: str
    start_period: int
    venue_id: str | None = None
    via: Literal["app", "chatbot"] = "app"  # only labels the activity log; never affects permissions


class ProposalOut(BaseModel):
    id: str
    message: str
    changes: list[Change]
    quality_before: int | None
    quality_after: int | None


class AuditOut(BaseModel):
    id: str
    at: float
    action: str
    source: str
    actor: str
    changes: list[Change]
    undone: bool
    can_undo: bool


NOT_PUBLISHED = "Your timetable hasn't been published yet. It appears here as soon as the College Admin publishes it."


def _current(ctx: Ctx, for_edit: bool = False):
    if ctx.state.timetable is None or not ctx.state.timetable.sessions:
        raise HTTPException(404, NOT_PUBLISHED if ctx.member.role in ("teacher", "student")
                            else "No timetable generated yet")
    if for_edit and not ctx.live:
        raise HTTPException(409, "The College Admin is preparing an updated timetable. Changes open again "
                                 "once it is published.")
    if for_edit and ctx.state.timetable.college_revision != ctx.state.college.revision:
        raise HTTPException(409, "The college data changed since this timetable was generated. "
                                 "Ask the College Admin to regenerate it first.")
    return ctx.state


def _session(state, session_id: str):
    s = next((x for x in state.timetable.sessions if x.id == session_id), None)
    if s is None:
        raise HTTPException(404, "Class not found in the current timetable")
    return s


@app.get("/api/orgs/{org}/timetable/sessions/{session_id}/options", response_model=list[MoveOption])
def get_move_options(session_id: str, ctx: Ctx = Depends(org_ctx)) -> list[MoveOption]:
    state = _current(ctx, for_edit=True)
    s = _session(state, session_id)
    allow(can_request_move(ctx.member, s) if ctx.member.role == "teacher" else can_edit_weekly(ctx.member, state.college, s))
    return move_options(state.college, state.timetable, session_id)


def _make_proposal(ctx: Ctx, state, session_id: str, day: str, start_period: int, venue_id: str | None = None,
                   source: str = "drag", request_id: str | None = None, requested_by: str = "") -> ProposalOut:
    """Repair, check permissions on everything that moves, and keep the result for Apply."""
    moved = _session(state, session_id)
    allow(can_edit_weekly(ctx.member, state.college, moved))
    if day not in state.college.days:
        raise HTTPException(422, f"{day} is not a working day")
    candidate, message = repair_move(state.college, state.timetable, session_id, day, start_period, venue_id)
    if candidate is None:
        raise HTTPException(422, message)
    changes = diff(state.college, state.timetable.sessions, candidate.sessions)
    changes.sort(key=lambda c: c.session_id != session_id)  # the class the user moved comes first
    # A Coordinator's move may not push other departments' classes around.
    for c in changes:
        s = next(x for x in state.timetable.sessions if x.id == c.session_id)
        if can_edit_weekly(ctx.member, state.college, s):
            raise HTTPException(403, "This change would also move another department's classes, "
                                     "so it needs the College Admin.")
    before = score(state.college, state.timetable.sessions, state.timetable.lunches).score
    after = score(state.college, candidate.sessions, candidate.lunches).score
    subj = state.college.subject(moved.subject_id).name
    secs = " + ".join(state.college.section(i).name for i in moved.section_ids)
    when = f"{day} {state.college.shift(moved.shift_id).periods[start_period].start}"
    action = f"Moved {subj} ({secs}) to {when}" + (f" (requested by {requested_by})" if requested_by else "")
    p = store.add_proposal(state.id, candidate, changes, message, action=action, created_by=ctx.user.id,
                           source=source, request_id=request_id)
    return ProposalOut(id=p.id, message=message, changes=changes, quality_before=before, quality_after=after)


@app.post("/api/orgs/{org}/proposals", response_model=ProposalOut, status_code=201)
def create_proposal(body: ProposalRequest, ctx: Ctx = Depends(org_ctx)) -> ProposalOut:
    state = _current(ctx, for_edit=True)
    return _make_proposal(ctx, state, body.session_id, body.day, body.start_period, body.venue_id,
                          source="chatbot" if body.via == "chatbot" else "drag")


class ChangeRequestIn(BaseModel):
    session_id: str
    day: str
    start_period: int
    reason: str = ""


class DeclineIn(BaseModel):
    note: str = ""


def _request_scope(ctx: Ctx) -> dict:
    role = ctx.member.role
    if role == "admin":
        return {}
    if role == "coordinator":
        return {"department_id": ctx.member.department_id}
    if role == "teacher":
        return {"teacher_id": ctx.member.teacher_id}
    raise HTTPException(403, "Students don't have change requests.")


@app.post("/api/orgs/{org}/change-requests", response_model=ChangeRequestOut, status_code=201)
def create_change_request(body: ChangeRequestIn, ctx: Ctx = Depends(org_ctx)) -> ChangeRequestOut:
    """A teacher asks for a permanent move. Checked now (it must be possible), decided by the Coordinator."""
    state = _current(ctx, for_edit=True)
    s = _session(state, body.session_id)
    allow(can_request_move(ctx.member, s))
    college = state.college
    if body.day not in college.days:
        raise HTTPException(422, f"{body.day} is not a working day")
    candidate, message = repair_move(college, state.timetable, s.id, body.day, body.start_period, None)
    if candidate is None:
        raise HTTPException(422, message)
    periods = college.shift(s.shift_id).periods
    secs = " + ".join(college.section(i).name for i in s.section_ids)
    summary = (f"{college.subject(s.subject_id).name} ({secs}): {s.day} {s.start} -> "
               f"{body.day} {periods[body.start_period].start}")
    depts = sorted({college.section(i).department_id for i in s.section_ids})
    req = change_requests.create(state.id, ctx.user.id, ctx.user.name, s.teacher_id, depts, s.id, body.day,
                                 body.start_period, summary, body.reason.strip())
    send(state.id, f"{ctx.user.name} asks to move a class", summary + (f". Reason: {req.reason}" if req.reason else ""),
         Audience(coordinator_departments=depts), ctx.user.id, link="/requests")
    return req


@app.get("/api/orgs/{org}/change-requests", response_model=list[ChangeRequestOut])
def list_change_requests(ctx: Ctx = Depends(org_ctx)) -> list[ChangeRequestOut]:
    return change_requests.listing(ctx.state.id, **_request_scope(ctx))


def _pending_request(ctx: Ctx, request_id: str):
    req = change_requests.get(ctx.state.id, request_id)
    if req is None:
        raise HTTPException(404, "Request not found.")
    if req.status != "pending":
        raise HTTPException(409, f"This request is already {req.status}.")
    if ctx.member.role == "coordinator" and ctx.member.department_id not in req.department_ids:
        raise HTTPException(404, "Request not found.")
    if ctx.member.role not in ("admin", "coordinator"):
        raise HTTPException(403, "Your Department Coordinator decides on change requests.")
    return req


@app.post("/api/orgs/{org}/change-requests/{request_id}/review", response_model=ProposalOut, status_code=201)
def review_change_request(request_id: str, ctx: Ctx = Depends(org_ctx)) -> ProposalOut:
    """Re-check the request against today's timetable and prepare it; Apply approves it."""
    req = _pending_request(ctx, request_id)
    state = _current(ctx, for_edit=True)
    if not any(x.id == req.session_id for x in state.timetable.sessions):
        raise HTTPException(409, "That class is no longer in the timetable. Decline the request.")
    try:
        return _make_proposal(ctx, state, req.session_id, req.day, req.start_period, source="teacher",
                              request_id=req.id, requested_by=req.teacher_name)
    except HTTPException as exc:
        if exc.status_code == 422:
            raise HTTPException(422, f"Not possible any more: {exc.detail} Decline it with a note, "
                                     "or ask the teacher for another time.") from None
        raise


@app.post("/api/orgs/{org}/change-requests/{request_id}/decline", response_model=ChangeRequestOut)
def decline_change_request(request_id: str, body: DeclineIn, ctx: Ctx = Depends(org_ctx)) -> ChangeRequestOut:
    req = _pending_request(ctx, request_id)
    out = change_requests.decide(ctx.state.id, req.id, "declined", ctx.user.name, body.note.strip())
    send(ctx.state.id, "Your change request was declined", req.summary + (f". Note: {out.note}" if out.note else ""),
         Audience(teacher_ids=[req.teacher_id]), ctx.user.id, link="/requests")
    return out


@app.post("/api/orgs/{org}/change-requests/{request_id}/withdraw", response_model=ChangeRequestOut)
def withdraw_change_request(request_id: str, ctx: Ctx = Depends(org_ctx)) -> ChangeRequestOut:
    req = change_requests.get(ctx.state.id, request_id)
    if req is None or req.teacher_id != ctx.member.teacher_id:
        raise HTTPException(404, "Request not found.")
    out = change_requests.decide(ctx.state.id, req.id, "withdrawn", ctx.user.name)
    if out is None:
        raise HTTPException(409, f"This request is already {req.status}.")
    return out


@app.post("/api/orgs/{org}/proposals/{proposal_id}/apply", response_model=TimetableOut)
def apply_proposal(proposal_id: str, ctx: Ctx = Depends(org_ctx)) -> TimetableOut:
    state = _current(ctx, for_edit=True)
    p = state.proposals.get(proposal_id)
    if p is None or p.based_on != state.version:
        store.pop_proposal(state.id, proposal_id)
        raise HTTPException(409, "This change is out of date: the timetable changed since it was prepared.")
    if p.created_by != ctx.user.id:
        raise HTTPException(403, "Only the person who prepared this change can apply it.")
    store.pop_proposal(state.id, proposal_id)
    if validate(state.college, p.timetable.sessions, p.timetable.lunches):  # golden rule #1, re-checked
        raise HTTPException(409, "This change would create a clash, so it wasn't applied.")
    before = state.timetable
    store.set_timetable(state.id, p.timetable, action=p.action, source=p.source, actor=ctx.user.name,
                        changes=p.changes)
    req = None
    if p.request_id:
        req = change_requests.decide(state.id, p.request_id, "approved", ctx.user.name)
        if req:
            send(state.id, "Your change request was approved", f"{req.summary}, every week from now on.",
                 Audience(teacher_ids=[req.teacher_id]), ctx.user.id)
    first = p.changes[0]
    others = len(p.changes) - 1
    body = f"{first.before} → {first.after}, every week from now on."
    if others:
        body += f" {others} other class{'es' if others > 1 else ''} moved to make room."
    notify_change(state.id, state.college, before, p.timetable, p.action, body, ctx.user.id,
                  skip_teacher=req.teacher_id if req else None)
    return _timetable_out(ctx)


@app.delete("/api/orgs/{org}/proposals/{proposal_id}", status_code=204, response_class=Response)
def discard_proposal(proposal_id: str, ctx: Ctx = Depends(org_ctx)) -> Response:
    p = ctx.state.proposals.get(proposal_id)
    if p and p.created_by == ctx.user.id:
        store.pop_proposal(ctx.state.id, proposal_id)
    return Response(status_code=204)


@app.get("/api/orgs/{org}/audit", response_model=list[AuditOut])
def get_audit(ctx: Ctx = Depends(org_ctx)) -> list[AuditOut]:
    allow(can_view_activity(ctx.member))
    undoable = store.last_undoable(ctx.state.id)
    return [
        AuditOut(id=e.id, at=e.at, action=e.action, source=e.source, actor=e.actor, changes=e.changes,
                 undone=e.undone, can_undo=e is undoable and not can_undo(ctx.member, e.actor))
        for e in reversed(ctx.state.audit)
    ]


# ---------------------------------------------------------------------------
# Attendance: teachers mark each class; students see where they stand
# ---------------------------------------------------------------------------

class RosterStudent(BaseModel):
    student_id: str
    roll_no: str
    name: str


class ClassAttendanceOut(BaseModel):
    occurrence_id: str
    session_id: str
    date: str
    subject: str
    sections: str
    start: str
    end: str
    venue: str
    roster: list[RosterStudent]
    absent: list[str]
    marked: bool
    marked_by: str = ""
    marked_at: float | None = None
    can_edit: bool
    note: str = ""


class AttendanceIn(BaseModel):
    session_id: str
    date: str
    absent: list[str] = []


def _today() -> str:
    return datetime.date.today().isoformat()


def _held_occurrence(state, session_id: str, d: str):
    """The class as it happened on date ``d`` (normal or moved there for the day), or 404."""
    try:
        datetime.date.fromisoformat(d)
    except ValueError:
        raise HTTPException(422, "Use a date like 2026-10-21") from None
    occ = next((o for o in occurrences(state.college, state.timetable, d)
                if o.session.id == session_id and o.status in ("normal", "moved_in")), None)
    if occ is None:
        raise HTTPException(404, "That class doesn't take place on this date (cancelled, moved or not that day).")
    return occ


def _attendance_access(ctx: Ctx, occ, d: str) -> tuple[bool, str]:
    """(may edit, reason if not). Teachers: own classes, today or up to a week back. Staff: their classes."""
    role = ctx.member.role
    if role == "student":
        raise HTTPException(403, "Students see their own attendance under My attendance.")
    if role == "teacher" and occ.session.teacher_id != ctx.member.teacher_id:
        raise HTTPException(403, "You can only take attendance for your own classes.")
    if role == "coordinator":
        allow(can_edit_one_day(ctx.member, ctx.state.college, occ.session))
    if d > _today():
        return False, "Attendance opens on the day of the class."
    if role == "teacher" and (datetime.date.fromisoformat(_today()) - datetime.date.fromisoformat(d)).days > attendance.EDIT_DAYS:
        return False, f"Older than {attendance.EDIT_DAYS} days: ask your Department Coordinator to correct it."
    return True, ""


def _class_out(ctx: Ctx, occ, d: str) -> ClassAttendanceOut:
    college = ctx.state.college
    s = occ.session
    rec = attendance.get(ctx.state.id, occ.occurrence_id)
    students = attendance.roster(college, s)
    if rec:  # the roster as it was that day
        by_id = {st.id: st for st in college.students}
        students = [by_id[i] for i in rec.roster if i in by_id]
    can_edit, note = _attendance_access(ctx, occ, d)
    return ClassAttendanceOut(
        occurrence_id=occ.occurrence_id, session_id=s.id, date=d, subject=college.subject(s.subject_id).name,
        sections=" + ".join(college.section(i).name for i in s.section_ids) + (
            f" · {next((b.name for i in s.section_ids for b in college.section(i).batches if b.id == s.batch_id), '')}"
            if s.batch_id else ""),
        start=s.start, end=s.end, venue=college.venue(s.venue_id).name if s.venue_id else "",
        roster=[RosterStudent(student_id=st.id, roll_no=st.roll_no, name=st.name)
                for st in sorted(students, key=lambda x: x.roll_no)],
        absent=rec.absent if rec else [], marked=rec is not None, marked_by=rec.marked_by if rec else "",
        marked_at=rec.marked_at if rec else None, can_edit=can_edit, note=note)


@app.get("/api/orgs/{org}/attendance/class", response_model=ClassAttendanceOut)
def get_class_attendance(session_id: str, date: str, ctx: Ctx = Depends(org_ctx)) -> ClassAttendanceOut:
    state = _current(ctx)
    return _class_out(ctx, _held_occurrence(state, session_id, date), date)


@app.put("/api/orgs/{org}/attendance/class", response_model=ClassAttendanceOut)
def save_class_attendance(body: AttendanceIn, ctx: Ctx = Depends(org_ctx)) -> ClassAttendanceOut:
    state = _current(ctx)
    occ = _held_occurrence(state, body.session_id, body.date)
    can_edit, note = _attendance_access(ctx, occ, body.date)
    if not can_edit:
        raise HTTPException(409, note)
    existing = attendance.get(state.id, occ.occurrence_id)
    roster_ids = existing.roster if existing else [st.id for st in attendance.roster(state.college, occ.session)]
    unknown = set(body.absent) - set(roster_ids)
    if unknown:
        raise HTTPException(422, "Some students marked absent aren't in this class.")
    attendance.save(state.id, attendance.new_record(occ.occurrence_id, occ.session, body.date, roster_ids,
                                                    body.absent, ctx.user.name))
    return _class_out(ctx, occ, body.date)


class TeacherClassOut(BaseModel):
    session_id: str
    date: str
    label: str  # "Thu 23 Oct"
    subject: str
    sections: str
    start: str
    end: str
    venue: str
    students: int
    marked: bool
    absent: int
    can_edit: bool


@app.get("/api/orgs/{org}/attendance/my-classes", response_model=list[TeacherClassOut])
def my_classes_attendance(ctx: Ctx = Depends(org_ctx)) -> list[TeacherClassOut]:
    """A teacher's classes from the last week up to today, newest first, with marked / not yet."""
    if ctx.member.role != "teacher" or not ctx.member.teacher_id:
        raise HTTPException(403, "This list is for teachers.")
    state = _current(ctx)
    college = state.college
    today = datetime.date.fromisoformat(_today())
    out = []
    for back in range(attendance.EDIT_DAYS + 1):
        d = (today - datetime.timedelta(days=back)).isoformat()
        for o in occurrences(college, state.timetable, d):
            if o.status not in ("normal", "moved_in") or o.session.teacher_id != ctx.member.teacher_id:
                continue
            rec = attendance.get(state.id, o.occurrence_id)
            out.append(TeacherClassOut(
                session_id=o.session.id, date=d, label=label(d), subject=college.subject(o.session.subject_id).name,
                sections=" + ".join(college.section(i).name for i in o.session.section_ids),
                start=o.session.start, end=o.session.end,
                venue=college.venue(o.session.venue_id).name if o.session.venue_id else "",
                students=len(rec.roster) if rec else len(attendance.roster(college, o.session)),
                marked=rec is not None, absent=len(rec.absent) if rec else 0, can_edit=True))
    return sorted(out, key=lambda c: (c.date, c.start), reverse=True)


@app.get("/api/orgs/{org}/attendance/me", response_model=attendance.StudentAttendance)
def my_attendance(ctx: Ctx = Depends(org_ctx)) -> attendance.StudentAttendance:
    if ctx.member.role != "student":
        raise HTTPException(403, "My attendance is for students.")
    me = next((st for st in ctx.state.college.students if st.email.lower() == ctx.member.email.lower()), None)
    if me is None:
        raise HTTPException(404, "Your name isn't on this college's student list yet.")
    return attendance.for_student(ctx.state.college, ctx.state.id, me.id)


class SectionAttendanceOut(BaseModel):
    section: str
    min_percent: int
    students: list[attendance.StudentRow]


@app.get("/api/orgs/{org}/attendance/sections/{section_id}", response_model=SectionAttendanceOut)
def section_attendance(section_id: str, ctx: Ctx = Depends(org_ctx)) -> SectionAttendanceOut:
    college = ctx.state.college
    sec = next((x for x in college.sections if x.id == section_id), None)
    if sec is None:
        raise HTTPException(404, "Section not found.")
    if ctx.member.role not in ("admin", "coordinator") or (
            ctx.member.role == "coordinator" and sec.department_id != ctx.member.department_id):
        raise HTTPException(403, "Department Coordinators see their own sections; the College Admin sees all.")
    return SectionAttendanceOut(section=sec.name, min_percent=college.attendance_min_percent,
                                students=attendance.for_section(college, ctx.state.id, section_id))


class AttendanceRuleIn(BaseModel):
    min_percent: int


class AttendanceRuleOut(BaseModel):
    min_percent: int
    message: str


@app.put("/api/orgs/{org}/attendance/rule", response_model=AttendanceRuleOut)
def set_attendance_rule(body: AttendanceRuleIn, ctx: Ctx = Depends(org_ctx)) -> AttendanceRuleOut:
    allow(can_manage_college(ctx.member))
    if not 1 <= body.min_percent <= 100:
        raise HTTPException(422, "Use a percentage between 1 and 100.")
    college = ctx.state.college
    store.update_college(ctx.state.id, college.model_copy(update={"attendance_min_percent": body.min_percent}),
                         bump=False)  # the timetable doesn't change
    return AttendanceRuleOut(min_percent=body.min_percent,
                             message=f"Saved. Students now need {body.min_percent}% attendance.")


@app.get("/api/orgs/{org}/notifications", response_model=FeedOut)
def get_notifications(ctx: Ctx = Depends(org_ctx)) -> FeedOut:
    return feed(ctx.member)


@app.post("/api/orgs/{org}/notifications/seen", status_code=204, response_class=Response)
def notifications_seen(ctx: Ctx = Depends(org_ctx)) -> Response:
    mark_seen(ctx.member)
    return Response(status_code=204)


class UndoRequest(BaseModel):
    entry_id: str | None = None  # undo exactly this change (refused if something changed after it)


@app.post("/api/orgs/{org}/audit/undo", response_model=TimetableOut)
def undo(body: UndoRequest | None = None, ctx: Ctx = Depends(org_ctx)) -> TimetableOut:
    entry = store.last_undoable(ctx.state.id)
    if entry is None:
        raise HTTPException(409, "Nothing to undo.")
    if body and body.entry_id and body.entry_id != entry.id:
        raise HTTPException(409, "Someone changed the timetable after this, so it can't be undone from here. "
                                 "Open Changes to undo step by step.")
    allow(can_undo(ctx.member, entry.actor))
    before = ctx.state.timetable
    store.undo_last(ctx.state.id, actor=ctx.user.name)
    if entry.source != "generate":
        notify_change(ctx.state.id, ctx.state.college, before, store.org(ctx.state.id).timetable,
                      f"Change undone: {entry.action}", "The class is back where it was.", ctx.user.id)
    return _timetable_out(ctx)


# ---------------------------------------------------------------------------
# One-day changes (overrides on real dates)
# ---------------------------------------------------------------------------

class WeekOut(BaseModel):
    days: list[DayInfo]
    occurrences: list[Occurrence]


class OverrideRequest(BaseModel):
    session_id: str
    date: str
    kind: str  # "cancel" | "move"
    to_date: str | None = None
    start_period: int | None = None
    reason: str = ""
    via: Literal["app", "chatbot"] = "app"  # only labels the activity log; never affects permissions


class OverrideOut(BaseModel):
    message: str
    timetable: TimetableOut


@app.get("/api/orgs/{org}/timetable/week", response_model=WeekOut)
def get_week(start: str, ctx: Ctx = Depends(org_ctx)) -> WeekOut:
    state = _current(ctx)
    try:
        days = week(state.college, start)
    except ValueError:
        raise HTTPException(422, "Use a date like 2026-10-21") from None
    occ = [o for d in days for o in occurrences(state.college, state.timetable, d.date)]
    if ctx.member.role not in ("admin", "coordinator"):
        visible = {s.id for s in visible_sessions(ctx.member, state.college, state.timetable)}
        mine = ctx.member.teacher_id if ctx.member.role == "teacher" else None
        # A substitute sees the classes they cover; the usual teacher still sees theirs (marked as covered).
        occ = [o for o in occ if o.session.id in visible or (mine and o.session.teacher_id == mine)]
    return WeekOut(days=days, occurrences=occ)


@app.get("/api/orgs/{org}/timetable/sessions/{session_id}/day-options", response_model=list[MoveOption])
def get_day_options(session_id: str, date: str, to_date: str, ctx: Ctx = Depends(org_ctx)) -> list[MoveOption]:
    state = _current(ctx, for_edit=True)
    allow(can_edit_one_day(ctx.member, state.college, _session(state, session_id)))
    return day_options(state.college, state.timetable, session_id, date, to_date)


@app.get("/api/orgs/{org}/timetable/sessions/{session_id}/makeup", response_model=list[MakeupOption])
def get_makeup_options(session_id: str, date: str, days: int = 7, ctx: Ctx = Depends(org_ctx)) -> list[MakeupOption]:
    """Makeup class finder: free times in the next ``days`` days for this class (teacher, students, room)."""
    state = _current(ctx, for_edit=True)
    allow(can_edit_one_day(ctx.member, state.college, _session(state, session_id)))
    return makeup_options(state.college, state.timetable, session_id, date, datetime.date.today().isoformat(),
                          days=max(1, min(days, 21)))


@app.post("/api/orgs/{org}/overrides", response_model=OverrideOut, status_code=201)
def create_override(body: OverrideRequest, ctx: Ctx = Depends(org_ctx)) -> OverrideOut:
    state = _current(ctx, for_edit=True)
    allow(can_edit_one_day(ctx.member, state.college, _session(state, body.session_id)))
    new, message, action = add_override(state.college, state.timetable, body.session_id, body.date, body.kind,
                                        body.to_date, body.start_period, body.reason, actor=ctx.user.name)
    if new is None:
        raise HTTPException(422, message)
    source = "chatbot" if body.via == "chatbot" else "teacher" if ctx.member.role == "teacher" else "one-day"
    before = state.timetable
    store.set_timetable(state.id, new, action=action, source=source, actor=ctx.user.name)
    notify_change(state.id, state.college, before, new, action,
                  f"{message} {('Reason: ' + body.reason) if body.reason else ''}".strip(), ctx.user.id)
    return OverrideOut(message=message, timetable=_timetable_out(ctx))


class BatchOverrideRequest(BaseModel):
    changes: list[OverrideRequest]
    title: str = ""  # one line for the activity log, e.g. "Dr. Kaur away on Thu 30 Oct"
    via: Literal["app", "chatbot"] = "app"


@app.post("/api/orgs/{org}/overrides/batch", response_model=OverrideOut, status_code=201)
def create_overrides(body: BatchOverrideRequest, ctx: Ctx = Depends(org_ctx)) -> OverrideOut:
    """Several one-day changes as one step: all of them or none, one activity entry, one notification."""
    state = _current(ctx, for_edit=True)
    if not 1 <= len(body.changes) <= 60:
        raise HTTPException(422, "Send between 1 and 60 changes at a time.")
    tt, messages, actions = state.timetable, [], []
    for ch in body.changes:
        s = _session(state, ch.session_id)
        allow(can_edit_one_day(ctx.member, state.college, s))
        new, message, action = add_override(state.college, tt, ch.session_id, ch.date, ch.kind, ch.to_date,
                                            ch.start_period, ch.reason, actor=ctx.user.name)
        if new is None:
            raise HTTPException(422, f"{state.college.subject(s.subject_id).name} on {label(ch.date)}: {message} "
                                     "Nothing was changed.")
        tt = new
        messages.append(message)
        actions.append(action)
    # Golden rule #1 on every real date this touches: nothing may clash and every section keeps its lunch.
    for d in sorted({ch.to_date or ch.date for ch in body.changes}):
        if validate(state.college, *one_day(state.college, tt, d), check_counts=False):
            raise HTTPException(422, f"These changes would create a clash on {label(d)}. Nothing was changed.")
    source = "chatbot" if body.via == "chatbot" else "teacher" if ctx.member.role == "teacher" else "one-day"
    action = body.title.strip()[:200] or (actions[0] if len(actions) == 1 else f"{len(actions)} one-day changes")
    before = state.timetable
    store.set_timetable(state.id, tt, action=action, source=source, actor=ctx.user.name)
    notify_change(state.id, state.college, before, tt, action, " ".join(messages)[:900], ctx.user.id)
    n = len(messages)
    return OverrideOut(message=messages[0] if n == 1 else f"{n} changes saved. Everyone affected is told.",
                       timetable=_timetable_out(ctx))


@app.delete("/api/orgs/{org}/overrides/{override_id}", response_model=OverrideOut)
def delete_override(override_id: str, ctx: Ctx = Depends(org_ctx)) -> OverrideOut:
    state = _current(ctx, for_edit=True)
    ov = next((o for o in state.timetable.overrides if o.id == override_id), None)
    if ov is None:
        raise HTTPException(404, "That change no longer exists.")
    allow(can_edit_one_day(ctx.member, state.college, _session(state, ov.session_id)))
    new, message = remove_override(state.college, state.timetable, override_id)
    if new is None:
        raise HTTPException(409, message)
    before = state.timetable
    store.set_timetable(state.id, new, action=message, source="one-day", actor=ctx.user.name)
    notify_change(state.id, state.college, before, new, message, "The class is back to its usual time.",
                  ctx.user.id)
    return OverrideOut(message=message + ".", timetable=_timetable_out(ctx))


# ---------------------------------------------------------------------------
# Setup: college settings (Admin), departments + shared rooms (Admin),
# one department's data (its Coordinator or the Admin), suggestions, Ready flow
# ---------------------------------------------------------------------------

class SetupSaved(BaseModel):
    college: College
    problems: list[str]
    warnings: list[str]


class DepartmentsRequest(BaseModel):
    departments: list[Department]
    shared_venues: list[Venue]


class SuggestRequest(BaseModel):
    allotment_ids: list[str] = []  # empty = every class of the department without a teacher


class AssignRequest(BaseModel):
    assignments: dict[str, str | None]  # allotment id -> teacher id


class ReadyRequest(BaseModel):
    ready: bool


class DepartmentReadiness(BaseModel):
    department_id: str
    name: str
    ready: bool
    by: str
    at: float | None
    sections: int
    teachers: int
    subjects: int
    classes: int
    without_teacher: int
    students: int


def _saved(state, college: College, bump: bool = True) -> SetupSaved:
    saved = store.update_college(state.id, college, bump=bump)
    return SetupSaved(college=saved, problems=check(saved), warnings=warnings(saved))


def _dept_access(ctx: Ctx, dept: str) -> None:
    if dept not in {d.id for d in ctx.state.college.departments}:
        raise HTTPException(404, "Department not found.")
    m = ctx.member
    allow("" if m.role == "admin" or (m.role == "coordinator" and m.department_id == dept)
          else "Only this department's Coordinator or the College Admin can do this.")


@app.get("/api/orgs/{org}/settings", response_model=Settings)
def get_settings(ctx: Ctx = Depends(org_ctx)) -> Settings:
    return settings_of(ctx.state.college)


@app.put("/api/orgs/{org}/settings", response_model=SetupSaved)
def put_settings(body: Settings, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    allow(can_manage_college(ctx.member))
    new, errs = apply_settings(ctx.state.college, body)
    if new is None:
        raise HTTPException(422, " ".join(errs))
    return _saved(ctx.state, new.model_copy(update={"setup_saved": True}))


@app.put("/api/orgs/{org}/departments", response_model=SetupSaved)
def put_departments(body: DepartmentsRequest, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    allow(can_manage_college(ctx.member))
    college = ctx.state.college
    keep = {d.id for d in body.departments}
    in_use = {s.department_id for s in college.sections} | {t.department_id for t in college.teachers}
    removed = sorted(in_use - keep)
    if removed:
        raise HTTPException(422, f"Department(s) {', '.join(removed)} still have sections or teachers. "
                                 "Remove those first.")
    if any(v.department_id for v in body.shared_venues):
        raise HTTPException(422, "Shared rooms can't belong to a department.")
    venues = [v for v in college.venues if v.department_id] + body.shared_venues
    new = college.model_copy(update={"departments": body.departments, "venues": venues})
    errs = structural_errors(new)
    if errs:
        raise HTTPException(422, " ".join(errs))
    return _saved(ctx.state, new)


@app.get("/api/orgs/{org}/departments/{dept}/data", response_model=DeptData)
def get_dept_data(dept: str, ctx: Ctx = Depends(org_ctx)) -> DeptData:
    _dept_access(ctx, dept)
    return dept_slice(ctx.state.college, dept)


@app.put("/api/orgs/{org}/departments/{dept}/data", response_model=SetupSaved)
def put_dept_data(dept: str, body: DeptData, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    _dept_access(ctx, dept)
    new, errs = merge_dept(ctx.state.college, dept, body, actor=ctx.user.name)
    if new is None:
        raise HTTPException(422, " ".join(errs))
    return _saved(ctx.state, new)


@app.post("/api/orgs/{org}/departments/{dept}/suggest", response_model=SuggestResult)
def suggest_teachers(dept: str, body: SuggestRequest, ctx: Ctx = Depends(org_ctx)) -> SuggestResult:
    _dept_access(ctx, dept)
    college = ctx.state.college
    mine = dept_slice(college, dept).allotments
    ids = body.allotment_ids or [a.id for a in mine if a.teacher_id is None]
    if not set(ids) <= {a.id for a in mine}:
        raise HTTPException(403, "You can only get suggestions for your own department's classes.")
    return suggest(college, ids)


@app.put("/api/orgs/{org}/departments/{dept}/allotments", response_model=SetupSaved)
def assign_teachers(dept: str, body: AssignRequest, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    """Approve teachers for the department's classes (after reviewing suggestions)."""
    _dept_access(ctx, dept)
    college = ctx.state.college
    mine = {a.id for a in dept_slice(college, dept).allotments}
    if not set(body.assignments) <= mine:
        raise HTTPException(403, "You can only assign teachers to your own department's classes.")
    teachers = {t.id for t in college.teachers}
    if any(t is not None and t not in teachers for t in body.assignments.values()):
        raise HTTPException(422, "Unknown teacher.")
    allotments = [a.model_copy(update={"teacher_id": body.assignments[a.id]}) if a.id in body.assignments else a
                  for a in college.allotments]
    return _saved(ctx.state, college.model_copy(update={"allotments": allotments}))


@app.post("/api/orgs/{org}/departments/{dept}/ready", response_model=SetupSaved)
def mark_ready(dept: str, body: ReadyRequest, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    _dept_access(ctx, dept)
    college = ctx.state.college
    if body.ready:
        mine = dept_slice(college, dept)
        missing = [a for a in mine.allotments if a.teacher_id is None]
        if not mine.sections:
            raise HTTPException(422, "Add this department's sections first.")
        if not mine.allotments:
            raise HTTPException(422, "Add this department's classes (who teaches which subject to which section) first.")
        if missing:
            raise HTTPException(422, f"{len(missing)} class(es) still have no teacher.")
    # Ready is a status, not timetable data: the current timetable stays up to date.
    return _saved(ctx.state, set_ready(college, dept, body.ready, ctx.user.name), bump=False)


@app.get("/api/orgs/{org}/readiness", response_model=list[DepartmentReadiness])
def readiness(ctx: Ctx = Depends(org_ctx)) -> list[DepartmentReadiness]:
    allow("" if ctx.member.role in ("admin", "coordinator") else "Only staff can see department readiness.")
    college = ctx.state.college
    out = []
    for d in college.departments:
        if ctx.member.role == "coordinator" and d.id != ctx.member.department_id:
            continue  # a Coordinator sees only their own department
        sl = dept_slice(college, d.id)
        st = college.department_status.get(d.id)
        out.append(DepartmentReadiness(
            department_id=d.id, name=d.name, ready=bool(st and st.ready), by=st.by if st else "",
            at=st.at if st else None, sections=len(sl.sections), teachers=len(sl.teachers),
            subjects=len(sl.subjects), classes=len(sl.allotments),
            without_teacher=sum(1 for a in sl.allotments if a.teacher_id is None), students=len(sl.students),
        ))
    return out


# ---------------------------------------------------------------------------
# Excel: template download (pre-filled) and import with row-level errors
# ---------------------------------------------------------------------------

class ImportOut(BaseModel):
    errors: list[RowError]
    counts: dict[str, int]
    problems: list[str] = []
    warnings: list[str] = []
    saved: bool = False


@app.get("/api/orgs/{org}/departments/{dept}/template")
def download_template(dept: str, ctx: Ctx = Depends(org_ctx)) -> Response:
    _dept_access(ctx, dept)
    data = excel_template(ctx.state.college, dept)
    name = f"timetabl-{ctx.state.id}-{dept}.xlsx"
    return Response(content=data, headers={"Content-Disposition": f'attachment; filename="{name}"'},
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/orgs/{org}/departments/{dept}/import", response_model=ImportOut)
async def import_excel(dept: str, file: UploadFile, commit: bool = False, ctx: Ctx = Depends(org_ctx)) -> ImportOut:
    """commit=false: check and preview only. commit=true: save if there are no row errors."""
    _dept_access(ctx, dept)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 5 MB.")
    result = excel_parse(ctx.state.college, dept, content)
    if result.errors:
        return ImportOut(errors=result.errors, counts=result.counts)
    new, errs = merge_dept(ctx.state.college, dept, result.data, actor=ctx.user.name)
    if new is None:
        return ImportOut(errors=[RowError(sheet="", row=0, message=e) for e in errs], counts=result.counts)
    if not commit:
        return ImportOut(errors=[], counts=result.counts, problems=check(new), warnings=warnings(new))
    saved = store.update_college(ctx.state.id, new)
    return ImportOut(errors=[], counts=result.counts, problems=check(saved), warnings=warnings(saved), saved=True)


@app.post("/api/orgs/{org}/departments/{dept}/import/marked")
async def import_marked(dept: str, file: UploadFile, ctx: Ctx = Depends(org_ctx)) -> Response:
    """The uploaded sheet back, with every problem row highlighted and explained in a note."""
    _dept_access(ctx, dept)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 5 MB.")
    result = excel_parse(ctx.state.college, dept, content)
    marked = mark_errors(content, result.errors)
    if marked is None:
        raise HTTPException(422, "This file isn't an Excel (.xlsx) file, so there is nothing to mark.")
    return Response(content=marked, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{dept}-with-problems-marked.xlsx"'})


@app.get("/api/orgs/{org}/departments/{dept}/year-list-template")
def year_list_template(dept: str, ctx: Ctx = Depends(org_ctx)) -> Response:
    _dept_access(ctx, dept)
    return Response(content=sectioning.template(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="year-list-{dept}.xlsx"'})


@app.post("/api/orgs/{org}/departments/{dept}/auto-sections", response_model=sectioning.SectioningOut)
async def auto_sections(dept: str, file: UploadFile, year: int, max_size: int = 60, batches: int = 2,
                        shift_id: str | None = None, mix_by: str | None = None, prefix: str | None = None,
                        commit: bool = False, ctx: Ctx = Depends(org_ctx)) -> sectioning.SectioningOut:
    """Split a whole-year student list into sections + lab batches. commit=false: preview only."""
    _dept_access(ctx, dept)
    college = ctx.state.college
    if not 1 <= year <= 8:
        raise HTTPException(422, "Year must be between 1 and 8.")
    if not 5 <= max_size <= 300:
        raise HTTPException(422, "Section size must be between 5 and 300.")
    if not 1 <= batches <= 6:
        raise HTTPException(422, "Lab batches must be between 1 and 6.")
    if shift_id and shift_id not in {s.id for s in college.shifts}:
        raise HTTPException(422, "Unknown shift.")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 5 MB.")
    rows, errors, columns = sectioning.parse(content)
    if errors:
        return sectioning.SectioningOut(errors=errors, columns=columns)
    if mix_by and mix_by not in columns:
        raise HTTPException(422, f"There is no column '{mix_by}' in the sheet.")
    plan, groups = sectioning.plan(college, dept, year, rows, max_size, batches, shift_id, mix_by or None, prefix)
    new, problems = sectioning.apply(college, dept, plan, groups, actor=ctx.user.name)
    if new is None or not commit:
        return sectioning.SectioningOut(errors=[], columns=columns, plan=plan, problems=problems)
    store.update_college(ctx.state.id, new)
    return sectioning.SectioningOut(errors=[], columns=columns, plan=plan, saved=True)


# ---------------------------------------------------------------------------
# Rules (Admin: college-wide; Coordinator: own department) and teacher block times
# ---------------------------------------------------------------------------

class RulesRequest(BaseModel):
    rules: list[Rule]


class BlockedRequest(BaseModel):
    blocked: list[TimeBlock]


class BlockedOut(BaseModel):
    blocked: list[TimeBlock]
    message: str


def _rule_errors(college: College, rules: list[Rule]) -> list[str]:
    errs = []
    depts = {d.id for d in college.departments}
    for r in rules:
        if r.kind not in ("no_classes", "max_per_day", "spread_lunch"):
            errs.append(f"Rule '{r.name}': unknown kind.")
        if r.kind == "spread_lunch" and r.mode != "try":
            errs.append(f"Rule '{r.name}': spreading lunch is a preference, so it is always a Try rule.")
        if r.mode not in ("must", "try") or not 1 <= r.weight <= 10:
            errs.append(f"Rule '{r.name}': mode must be must/try and weight 1-10.")
        if r.department_id and r.department_id not in depts:
            errs.append(f"Rule '{r.name}': unknown department.")
        if r.kind == "max_per_day" and not (r.max_periods and r.max_periods > 0):
            errs.append(f"Rule '{r.name}': set the maximum periods per day.")
        if r.kind == "no_classes" and not (r.after or r.before or r.days):
            errs.append(f"Rule '{r.name}': choose the days and/or times with no classes.")
        if any(d not in college.days for d in r.days):
            errs.append(f"Rule '{r.name}': uses a day that isn't a working day.")
    if len({r.id for r in rules}) != len(rules):
        errs.append("Two rules have the same id.")
    return errs


@app.get("/api/orgs/{org}/rules", response_model=list[Rule])
def get_rules(ctx: Ctx = Depends(org_ctx)) -> list[Rule]:
    return ctx.state.college.rules


@app.put("/api/orgs/{org}/rules", response_model=SetupSaved)
def put_rules(body: RulesRequest, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    m, college = ctx.member, ctx.state.college
    if m.role == "coordinator":
        # Coordinators may only add / change / remove their own department's rules.
        theirs = lambda rs: sorted((r.model_dump_json() for r in rs if r.department_id != m.department_id))  # noqa: E731
        if theirs(body.rules) != theirs(college.rules):
            raise HTTPException(403, "Coordinators can only change their own department's rules.")
    else:
        allow(can_manage_college(m))
    errs = _rule_errors(college, body.rules)
    if errs:
        raise HTTPException(422, " ".join(errs))
    return _saved(ctx.state, college.model_copy(update={"rules": body.rules}))


@app.get("/api/orgs/{org}/me/blocked", response_model=BlockedOut)
def my_blocked(ctx: Ctx = Depends(org_ctx)) -> BlockedOut:
    tid = ctx.member.teacher_id
    if ctx.member.role != "teacher" or not tid:
        raise HTTPException(403, "Only teachers linked to the timetable have block times.")
    return BlockedOut(blocked=ctx.state.college.teacher(tid).blocked, message="")


@app.put("/api/orgs/{org}/me/blocked", response_model=BlockedOut)
def set_my_blocked(body: BlockedRequest, ctx: Ctx = Depends(org_ctx)) -> BlockedOut:
    """Teachers block times they can't teach. Confirmed instantly when it doesn't clash with their lectures."""
    tid = ctx.member.teacher_id
    if ctx.member.role != "teacher" or not tid:
        raise HTTPException(403, "Only teachers linked to the timetable can set block times.")
    college = ctx.state.college
    for b in body.blocked:
        if b.day not in college.days or not (b.start < b.end):
            raise HTTPException(422, f"Block {b.day} {b.start}-{b.end} isn't a valid working-day time range.")
    tt = store.org(ctx.state.id).timetable  # the real current one, also when a newer draft waits
    if tt and tt.sessions:
        def _min(t: str) -> int:
            h, mm = t.split(":")
            return int(h) * 60 + int(mm)
        for b in body.blocked:
            hit = next((s for s in tt.sessions if s.teacher_id == tid and s.day == b.day
                        and _min(s.start) < _min(b.end) and _min(b.start) < _min(s.end)), None)
            if hit:
                subj = college.subject(hit.subject_id).name
                raise HTTPException(409, f"You teach {subj} on {hit.day} {hit.start}-{hit.end}. Ask your Department "
                                         "Coordinator to move it first, or mark a one-day change for a single day.")
    teachers = [t.model_copy(update={"blocked": body.blocked}) if t.id == tid else t for t in college.teachers]
    saved = store.update_college(ctx.state.id, college.model_copy(update={"teachers": teachers}), bump=False)
    added = [b for b in body.blocked if b not in college.teacher(tid).blocked]
    if added:
        when = ", ".join(f"{b.day} {b.start}-{b.end}" for b in added)
        send(ctx.state.id, f"{ctx.user.name} blocked {when}",
             "Confirmed automatically: it doesn't clash with their lectures.",
             Audience(coordinator_departments=[college.teacher(tid).department_id], roles=["admin"]),
             ctx.user.id, link="/departments")
    return BlockedOut(blocked=saved.teacher(tid).blocked,
                      message="Saved. Your blocked times are confirmed and the next timetable will respect them.")


class SectionShiftsRequest(BaseModel):
    shifts: dict[str, str]  # section id -> shift id


@app.put("/api/orgs/{org}/section-shifts", response_model=SetupSaved)
def set_section_shifts(body: SectionShiftsRequest, ctx: Ctx = Depends(org_ctx)) -> SetupSaved:
    """Two shifts: which sections study in which shift (e.g. 1st years Morning, the rest Evening)."""
    allow(can_manage_college(ctx.member))
    college = ctx.state.college
    shifts = {s.id for s in college.shifts}
    known = {s.id for s in college.sections}
    if not set(body.shifts) <= known or not set(body.shifts.values()) <= shifts:
        raise HTTPException(422, "Unknown section or shift.")
    sections = [s.model_copy(update={"shift_id": body.shifts.get(s.id, s.shift_id)}) for s in college.sections]
    new = college.model_copy(update={"sections": sections})
    errs = structural_errors(new)
    if errs:
        raise HTTPException(422, " ".join(errs))
    return _saved(ctx.state, new)


# ---------------------------------------------------------------------------
# Assistant facts (read-only, safe for every member) and insights (staff)
# ---------------------------------------------------------------------------

def _today_now() -> tuple[str, str]:
    now = time.localtime()
    return time.strftime("%Y-%m-%d", now), time.strftime("%H:%M", now)


@app.get("/api/orgs/{org}/free-rooms", response_model=list[FreeRoom])
def get_free_rooms(date: str | None = None, at: str | None = None, min_seats: int = 0,
                   ctx: Ctx = Depends(org_ctx)) -> list[FreeRoom]:
    state = _current(ctx)
    today, now = _today_now()
    return free_rooms(state.college, state.timetable, date or today, at or now, min_seats)


@app.get("/api/orgs/{org}/teachers/{teacher_id}/now", response_model=TeacherNow)
def get_teacher_now(teacher_id: str, date: str | None = None, at: str | None = None,
                    ctx: Ctx = Depends(org_ctx)) -> TeacherNow:
    state = _current(ctx)
    if teacher_id not in {t.id for t in state.college.teachers}:
        raise HTTPException(404, "Teacher not found.")
    today, now = _today_now()
    return teacher_now(state.college, state.timetable, teacher_id, date or today, at or now)


@app.get("/api/orgs/{org}/timetable/sessions/{session_id}/explain", response_model=Explanation)
def explain_session(session_id: str, ctx: Ctx = Depends(org_ctx)) -> Explanation:
    state = _current(ctx)
    s = _session(state, session_id)
    if ctx.member.role not in ("admin", "coordinator") and s.id not in {
        x.id for x in visible_sessions(ctx.member, state.college, state.timetable)
    }:
        raise HTTPException(404, "Class not found in your timetable.")
    return explain(state.college, state.timetable, session_id)


@app.get("/api/orgs/{org}/insights", response_model=list[Insight])
def get_insights(ctx: Ctx = Depends(org_ctx)) -> list[Insight]:
    allow("" if ctx.member.role in ("admin", "coordinator") else "Insights are for staff.")
    state = ctx.state
    if state.timetable is None or state.timetable.college_revision != state.college.revision:
        return []
    return insights(state.college, state.timetable)


# Session B routers (own files; kept at the end so they merge cleanly)
from app.routers.reschedule import router as reschedule_router  # noqa: E402
from app.routers.venue_events import router as venue_events_router  # noqa: E402
from app.routers.notices import router as notices_router  # noqa: E402

app.include_router(reschedule_router)
app.include_router(venue_events_router)
app.include_router(notices_router)
