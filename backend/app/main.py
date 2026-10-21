"""Timetabl.ai backend API.

Stage 2: read the college, generate a timetable in the background, read the
current timetable with its quality report and validator result.
"""

from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
            store.set_timetable(org, tt)
            job.status = "done"
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
