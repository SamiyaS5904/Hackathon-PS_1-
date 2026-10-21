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
class Proposal:
    id: str
    timetable: Timetable  # the candidate, already validated
    changes: list  # list[Change]
    message: str
    based_on: int  # timetable version it was computed from
    action: str = "Edited timetable"  # audit sentence once applied


@dataclass
class AuditEntry:
    id: str
    at: float
    action: str  # human sentence, e.g. "Moved Data Structures (CSE-2A) to Thu 11:00"
    source: str  # "generate" | "drag" | "chatbot" | "teacher" | "system"
    actor: str
    changes: list  # list[Change]
    before: Timetable | None
    after: Timetable
    undone: bool = False


@dataclass
class OrgState:
    college: College
    timetable: Timetable | None = None
    version: int = 0
    proposals: dict[str, Proposal] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)


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

    def set_timetable(self, org: str, tt: Timetable, action: str, source: str, actor: str = "Admin",
                      changes: list | None = None) -> AuditEntry:
        """Replace the current timetable and record it in the audit log."""
        with self._lock:
            state = self._orgs[org]
            entry = AuditEntry(id=uuid.uuid4().hex[:10], at=time.time(), action=action, source=source, actor=actor,
                               changes=changes or [], before=state.timetable, after=tt)
            state.timetable = tt
            state.version += 1
            state.proposals.clear()  # proposals computed on an older version are stale
            state.audit.append(entry)
            return entry

    def add_proposal(self, org: str, tt: Timetable, changes: list, message: str, action: str) -> Proposal:
        with self._lock:
            state = self._orgs[org]
            p = Proposal(id=uuid.uuid4().hex[:10], timetable=tt, changes=changes, message=message,
                         based_on=state.version, action=action)
            state.proposals[p.id] = p
            return p

    def pop_proposal(self, org: str, pid: str) -> Proposal | None:
        with self._lock:
            return self._orgs[org].proposals.pop(pid, None)

    def undo_last(self, org: str) -> AuditEntry | None:
        """Undo the most recent change that isn't undone yet (generation can't be undone)."""
        with self._lock:
            state = self._orgs[org]
            entry = next((e for e in reversed(state.audit) if not e.undone and e.source != "undo"), None)
            if entry is None or entry.before is None:
                return None
            entry.undone = True
            state.timetable = entry.before
            state.version += 1
            state.proposals.clear()
            state.audit.append(AuditEntry(id=uuid.uuid4().hex[:10], at=time.time(), action=f"Undid: {entry.action}",
                                          source="undo", actor=entry.actor, changes=[], before=entry.after,
                                          after=entry.before))
            return entry

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
