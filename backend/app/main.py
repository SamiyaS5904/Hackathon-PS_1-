"""Timetabl.ai backend API.

Stage 2: read the college, generate a timetable in the background, read the
current timetable with its quality report and validator result.
"""

from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.edits.moves import Change, MoveOption, diff, move_options, repair_move
from app.models.domain import College, Timetable
from app.solver.feasibility import check, warnings
from app.solver.generate import generate
from app.solver.quality import QualityReport, score
from app.store import store
from app.validator.check import Violation, validate


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.seed_demo()
    yield


app = FastAPI(title="Timetabl.ai API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    time_limit: float = 45.0


class JobOut(BaseModel):
    id: str
    status: str
    elapsed: float
    error: str | None = None


class TimetableOut(BaseModel):
    timetable: Timetable
    quality: QualityReport | None
    violations: list[Violation]


class PrecheckOut(BaseModel):
    problems: list[str]
    warnings: list[str]


def _org(org: str):
    state = store.org(org)
    if state is None:
        raise HTTPException(404, f"College '{org}' not found")
    return state


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/orgs/{org}/college", response_model=College)
def get_college(org: str) -> College:
    return _org(org).college


@app.get("/api/orgs/{org}/precheck", response_model=PrecheckOut)
def precheck(org: str) -> PrecheckOut:
    college = _org(org).college
    return PrecheckOut(problems=check(college), warnings=warnings(college))


@app.post("/api/orgs/{org}/timetable/generate", response_model=JobOut, status_code=202)
def start_generation(org: str, body: GenerateRequest) -> JobOut:
    college = _org(org).college
    if store.running_job(org):
        raise HTTPException(409, "A timetable is already being generated for this college.")
    job = store.new_job(org)

    def run() -> None:
        try:
            tt = generate(college, time_limit=max(5.0, min(body.time_limit, 300.0)))
            if tt.sessions:
                store.set_timetable(org, tt, action=f"Generated timetable ({len(tt.sessions)} classes)",
                                    source="generate")
            else:
                job.error = "; ".join(tt.messages) or "No timetable could be built."
            job.status = "done" if tt.sessions else "failed"
        except Exception as exc:  # surfaced to the UI, never swallowed
            job.status, job.error = "failed", str(exc)
        finally:
            job.finished_at = time.time()

    threading.Thread(target=run, daemon=True).start()
    return JobOut(id=job.id, status=job.status, elapsed=0.0)


@app.get("/api/orgs/{org}/jobs/{job_id}", response_model=JobOut)
def get_job(org: str, job_id: str) -> JobOut:
    job = store.job(job_id)
    if job is None or job.org != org:
        raise HTTPException(404, "Job not found")
    end = job.finished_at or time.time()
    return JobOut(id=job.id, status=job.status, elapsed=round(end - job.started_at, 1), error=job.error)


@app.get("/api/orgs/{org}/timetable", response_model=TimetableOut)
def get_timetable(org: str) -> TimetableOut:
    state = _org(org)
    tt = state.timetable
    if tt is None:
        raise HTTPException(404, "No timetable generated yet")
    quality = score(state.college, tt.sessions, tt.lunches) if tt.sessions else None
    violations = validate(state.college, tt.sessions, tt.lunches) if tt.sessions else []
    return TimetableOut(timetable=tt, quality=quality, violations=violations)


# ---------------------------------------------------------------------------
# Stage 3: editing (move options, proposals with repair, apply, audit, undo)
# ---------------------------------------------------------------------------

class ProposalRequest(BaseModel):
    session_id: str
    day: str
    start_period: int
    venue_id: str | None = None


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


def _current(org: str):
    state = _org(org)
    if state.timetable is None or not state.timetable.sessions:
        raise HTTPException(404, "No timetable generated yet")
    return state


def _session(state, session_id: str):
    s = next((x for x in state.timetable.sessions if x.id == session_id), None)
    if s is None:
        raise HTTPException(404, "Class not found in the current timetable")
    return s


@app.get("/api/orgs/{org}/timetable/sessions/{session_id}/options", response_model=list[MoveOption])
def get_move_options(org: str, session_id: str) -> list[MoveOption]:
    state = _current(org)
    _session(state, session_id)
    return move_options(state.college, state.timetable, session_id)


@app.post("/api/orgs/{org}/proposals", response_model=ProposalOut, status_code=201)
def create_proposal(org: str, body: ProposalRequest) -> ProposalOut:
    state = _current(org)
    moved = _session(state, body.session_id)
    if body.day not in state.college.days:
        raise HTTPException(422, f"{body.day} is not a working day")
    candidate, message = repair_move(state.college, state.timetable, body.session_id, body.day, body.start_period,
                                     body.venue_id)
    if candidate is None:
        raise HTTPException(422, message)
    changes = diff(state.college, state.timetable.sessions, candidate.sessions)
    changes.sort(key=lambda c: c.session_id != body.session_id)  # the class the user moved comes first
    before = score(state.college, state.timetable.sessions, state.timetable.lunches).score
    after = score(state.college, candidate.sessions, candidate.lunches).score
    subj = state.college.subject(moved.subject_id).name
    secs = " + ".join(state.college.section(i).name for i in moved.section_ids)
    when = f"{body.day} {state.college.shift(moved.shift_id).periods[body.start_period].start}"
    p = store.add_proposal(org, candidate, changes, message, action=f"Moved {subj} ({secs}) to {when}")
    return ProposalOut(id=p.id, message=message, changes=changes, quality_before=before, quality_after=after)


@app.post("/api/orgs/{org}/proposals/{proposal_id}/apply", response_model=TimetableOut)
def apply_proposal(org: str, proposal_id: str) -> TimetableOut:
    state = _current(org)
    p = store.pop_proposal(org, proposal_id)
    if p is None or p.based_on != state.version:
        raise HTTPException(409, "This change is out of date: the timetable changed since it was prepared.")
    if validate(state.college, p.timetable.sessions, p.timetable.lunches):  # golden rule #1, re-checked
        raise HTTPException(409, "This change would create a clash, so it wasn't applied.")
    store.set_timetable(org, p.timetable, action=p.action, source="drag",
                        changes=p.changes)
    return get_timetable(org)


@app.delete("/api/orgs/{org}/proposals/{proposal_id}", status_code=204, response_class=Response)
def discard_proposal(org: str, proposal_id: str) -> Response:
    _org(org)
    store.pop_proposal(org, proposal_id)
    return Response(status_code=204)


@app.get("/api/orgs/{org}/audit", response_model=list[AuditOut])
def get_audit(org: str) -> list[AuditOut]:
    state = _org(org)
    undoable = next((e for e in reversed(state.audit) if not e.undone and e.source != "undo"), None)
    return [
        AuditOut(id=e.id, at=e.at, action=e.action, source=e.source, actor=e.actor, changes=e.changes,
                 undone=e.undone, can_undo=e is undoable and e.before is not None)
        for e in reversed(state.audit)
    ]


@app.post("/api/orgs/{org}/audit/undo", response_model=TimetableOut)
def undo(org: str) -> TimetableOut:
    _org(org)
    if store.undo_last(org) is None:
        raise HTTPException(409, "Nothing to undo.")
    return get_timetable(org)
