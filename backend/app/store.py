"""In-memory store (Stage 2-3). Replaced by Supabase in Stage 4.

Holds, per organisation: the college data, the current timetable and
generation jobs. Thread-safe because generation runs in a worker thread.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from app.models.domain import College, Timetable
from app.seed.demo_college import build_demo_college


@dataclass
class Job:
    id: str
    org: str
    status: str = "running"  # running | done | failed
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None


@dataclass
class OrgState:
    college: College
    timetable: Timetable | None = None


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._orgs: dict[str, OrgState] = {}
        self._jobs: dict[str, Job] = {}

    def seed_demo(self) -> None:
        with self._lock:
            self._orgs["demo"] = OrgState(college=build_demo_college())

    def org(self, org: str) -> OrgState | None:
        with self._lock:
            return self._orgs.get(org)

    def set_timetable(self, org: str, tt: Timetable) -> None:
        with self._lock:
            self._orgs[org].timetable = tt

    def new_job(self, org: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], org=org)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def running_job(self, org: str) -> Job | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j.org == org and j.status == "running"), None)


store = Store()
