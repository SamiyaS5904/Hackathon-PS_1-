"""Per-college state, persisted in the database (SQLite locally, Supabase Postgres in production).

Kept in memory for speed and written through on every change. Holds, per
organisation: the college data, the current timetable (with one-day overrides),
the audit log, and short-lived proposals and generation jobs (memory only).
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from app.db.models import AuditRow, OrgRow, SessionLocal, TimetableRow, init_db
from app.models.domain import College, Timetable


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
    created_by: str = ""  # user id
    source: str = "drag"  # how it was made, for the activity log: drag | chatbot


@dataclass
class AuditEntry:
    id: str
    at: float
    action: str  # human sentence, e.g. "Moved Data Structures (CSE-2A) to Thu 11:00"
    source: str  # "generate" | "drag" | "one-day" | "chatbot" | "teacher" | "undo"
    actor: str
    changes: list  # list[Change] (or dicts once loaded from the database)
    before: Timetable | None
    after: Timetable
    undone: bool = False


@dataclass
class OrgState:
    id: str
    name: str
    college: College
    is_demo: bool = False
    timetable: Timetable | None = None
    version: int = 0
    proposals: dict[str, Proposal] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)


def _dump(changes: list) -> list:
    return [c.model_dump() if hasattr(c, "model_dump") else c for c in changes]


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (s or "college")[:48]


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._orgs: dict[str, OrgState] = {}
        self._jobs: dict[str, Job] = {}

    # ---- loading -------------------------------------------------------
    def load(self) -> None:
        init_db()
        with SessionLocal() as db, self._lock:
            self._orgs.clear()
            for row in db.scalars(select(OrgRow)):
                self._orgs[row.id] = OrgState(id=row.id, name=row.name, college=College.model_validate(row.college),
                                              is_demo=row.is_demo)
            for row in db.scalars(select(TimetableRow)):
                if row.org_id in self._orgs:
                    st = self._orgs[row.org_id]
                    st.timetable, st.version = Timetable.model_validate(row.data), row.version
            for row in db.scalars(select(AuditRow).order_by(AuditRow.seq)):
                if row.org_id in self._orgs:
                    self._orgs[row.org_id].audit.append(AuditEntry(
                        id=row.id, at=row.at, action=row.action, source=row.source, actor=row.actor,
                        changes=row.changes, before=Timetable.model_validate(row.before) if row.before else None,
                        after=Timetable.model_validate(row.after), undone=row.undone,
                    ))

    # ---- organisations ------------------------------------------------
    def org(self, org: str) -> OrgState | None:
        with self._lock:
            return self._orgs.get(org)

    def org_ids(self) -> list[str]:
        with self._lock:
            return list(self._orgs)

    def create_org(self, name: str, college: College, is_demo: bool = False, slug: str | None = None) -> OrgState:
        with self._lock, SessionLocal() as db:
            base = slug or slugify(name)
            oid, n = base, 2
            while oid in self._orgs or db.get(OrgRow, oid):
                oid, n = f"{base}-{n}", n + 1
            college = college.model_copy(update={"id": oid, "name": name})
            db.add(OrgRow(id=oid, name=name, college=college.model_dump(mode="json"), is_demo=is_demo))
            db.commit()
            state = OrgState(id=oid, name=name, college=college, is_demo=is_demo)
            self._orgs[oid] = state
            return state

    def update_college(self, org: str, college: College, bump: bool = True) -> College:
        """Save new college data. Bumps the revision (older timetables become out of date) unless the
        change is known to keep the current timetable valid (e.g. a clash-free teacher block time)."""
        with self._lock, SessionLocal() as db:
            old_rev = self._orgs[org].college.revision
            college = college.model_copy(update={"revision": old_rev + 1 if bump else old_rev})
            row = db.get(OrgRow, org)
            row.college = college.model_dump(mode="json")
            db.commit()
            self._orgs[org].college = college
            return college

    # ---- timetable + audit --------------------------------------------
    def _persist_timetable(self, db, state: OrgState) -> None:
        row = db.get(TimetableRow, state.id)
        data = state.timetable.model_dump(mode="json")
        if row is None:
            db.add(TimetableRow(org_id=state.id, version=state.version, data=data, updated_at=time.time()))
        else:
            row.version, row.data, row.updated_at = state.version, data, time.time()

    def _persist_audit(self, db, state: OrgState, entry: AuditEntry) -> None:
        db.add(AuditRow(
            id=entry.id, org_id=state.id, seq=len(state.audit), at=entry.at, action=entry.action,
            source=entry.source, actor=entry.actor, changes=_dump(entry.changes),
            before=entry.before.model_dump(mode="json") if entry.before else None,
            after=entry.after.model_dump(mode="json"), undone=entry.undone,
        ))

    def set_timetable(self, org: str, tt: Timetable, action: str, source: str, actor: str = "Admin",
                      changes: list | None = None) -> AuditEntry:
        """Replace the current timetable and record it in the audit log."""
        with self._lock, SessionLocal() as db:
            state = self._orgs[org]
            entry = AuditEntry(id=uuid.uuid4().hex[:10], at=time.time(), action=action, source=source, actor=actor,
                               changes=changes or [], before=state.timetable, after=tt)
            state.timetable = tt
            state.version += 1
            state.proposals.clear()  # proposals computed on an older version are stale
            state.audit.append(entry)
            self._persist_timetable(db, state)
            self._persist_audit(db, state, entry)
            db.commit()
            return entry

    def add_proposal(self, org: str, tt: Timetable, changes: list, message: str, action: str,
                     created_by: str = "", source: str = "drag") -> Proposal:
        with self._lock:
            state = self._orgs[org]
            p = Proposal(id=uuid.uuid4().hex[:10], timetable=tt, changes=changes, message=message,
                         based_on=state.version, action=action, created_by=created_by, source=source)
            state.proposals[p.id] = p
            return p

    def pop_proposal(self, org: str, pid: str) -> Proposal | None:
        with self._lock:
            return self._orgs[org].proposals.pop(pid, None)

    def last_undoable(self, org: str) -> AuditEntry | None:
        with self._lock:
            state = self._orgs[org]
            entry = next((e for e in reversed(state.audit) if not e.undone and e.source != "undo"), None)
            return entry if entry and entry.before is not None else None

    def undo_last(self, org: str, actor: str = "Admin") -> AuditEntry | None:
        """Undo the most recent change that isn't undone yet (the first generation can't be undone)."""
        with self._lock, SessionLocal() as db:
            state = self._orgs[org]
            entry = self.last_undoable(org)
            if entry is None:
                return None
            entry.undone = True
            row = db.get(AuditRow, entry.id)
            if row:
                row.undone = True
            state.timetable = entry.before
            state.version += 1
            state.proposals.clear()
            undo = AuditEntry(id=uuid.uuid4().hex[:10], at=time.time(), action=f"Undid: {entry.action}",
                              source="undo", actor=actor, changes=[], before=entry.after, after=entry.before)
            state.audit.append(undo)
            self._persist_timetable(db, state)
            self._persist_audit(db, state, undo)
            db.commit()
            return entry

    # ---- generation jobs (memory only) -----------------------------------
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
