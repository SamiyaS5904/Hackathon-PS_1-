"""Super Admin (platform owner): every college at a glance, plans and pauses (root CLAUDE.md §4).

The platform owner manages tenants, never college data: they see each college's size, setup progress,
timetable state, adoption (accounts, attendance, bookings) and health flags, and they can change a
college's plan label, make it read-only, or pause it. Members of a paused college get a plain 403; a
read-only college can be viewed but not changed.

Who is a platform owner: emails in SUPERADMIN_EMAILS, plus the demo owner (owner@demo.timetabl.ai) when
DEMO_PLATFORM_OWNER is on (the default, for demos; set it to 0 in production).
"""

from __future__ import annotations

import threading
import time

from pydantic import BaseModel
from sqlalchemy import func, select

from app import attendance, bookings
from app.core.config import DEMO_PLATFORM_OWNER, SUPERADMIN_EMAILS
from app.db.models import MembershipRow, PlatformOrgRow, SessionLocal, UserRow
from app.store import OrgState, store

DEMO_OWNER_EMAIL = "owner@demo.timetabl.ai"
PLANS = ("trial", "pro", "campus")
STATUSES = ("active", "read_only", "paused")
DAY = 86400.0


def is_owner(user: UserRow | None) -> bool:
    if user is None:
        return False
    email = user.email.lower()
    return email in SUPERADMIN_EMAILS or (DEMO_PLATFORM_OWNER and email == DEMO_OWNER_EMAIL)


# ---- plan / status (cached; changed only by the platform owner) ---------------------------------------

class OrgSettings(BaseModel):
    plan: str = "trial"
    status: str = "active"
    note: str = ""
    updated_at: float | None = None
    updated_by: str = ""


_lock = threading.Lock()
_settings: dict[str, OrgSettings] | None = None


def _all_settings() -> dict[str, OrgSettings]:
    global _settings
    with _lock:
        if _settings is not None:
            return _settings
    with SessionLocal() as db:
        rows = db.scalars(select(PlatformOrgRow)).all()
    loaded = {r.org_id: OrgSettings(plan=r.plan, status=r.status, note=r.note, updated_at=r.updated_at,
                                    updated_by=r.updated_by) for r in rows}
    with _lock:
        if _settings is None:
            _settings = loaded
        return _settings


def settings(org: str) -> OrgSettings:
    return _all_settings().get(org, OrgSettings())


def status_of(org: str) -> str:
    return settings(org).status


def update(org: str, by: str, plan: str | None = None, status: str | None = None,
           note: str | None = None) -> OrgSettings:
    cur = settings(org)
    new = cur.model_copy(update={k: v for k, v in {"plan": plan, "status": status, "note": note}.items()
                                 if v is not None} | {"updated_at": time.time(), "updated_by": by})
    with SessionLocal() as db:  # rare, and must survive a restart at once: written directly
        row = db.get(PlatformOrgRow, org)
        if row is None:
            db.add(PlatformOrgRow(org_id=org, plan=new.plan, status=new.status, note=new.note,
                                  updated_at=new.updated_at, updated_by=by))
        else:
            row.plan, row.status, row.note, row.updated_at, row.updated_by = (new.plan, new.status, new.note,
                                                                               new.updated_at, by)
        db.commit()
    _all_settings()[org] = new
    return new


# ---- overview ---------------------------------------------------------------------------------------

class CollegeSummary(BaseModel):
    id: str
    name: str
    is_demo: bool
    created_at: float
    plan: str
    status: str
    note: str
    stage: str  # "Setting up" | "Collecting data" | "Ready to generate" | "Draft" | "Live" | "Out of date"
    departments: int
    departments_ready: int
    sections: int
    teachers: int
    students: int
    accounts: int  # people who can log in (staff invited + students who logged in)
    classes: int  # classes in the current timetable
    published_at: float | None
    attendance_marked: int
    bookings: int
    last_activity: float
    flags: list[str]  # plain-language health notes, most important first
    needs_attention: bool


class PlatformOverview(BaseModel):
    colleges: int
    live: int
    needs_attention: int
    students: int
    teachers: int
    sections: int
    classes: int
    accounts: int
    attendance_marked: int
    bookings: int
    plans: dict[str, int]
    items: list[CollegeSummary]


def _accounts() -> dict[str, int]:
    with SessionLocal() as db:
        rows = db.execute(select(MembershipRow.org_id, func.count()).group_by(MembershipRow.org_id)).all()
    return {org: n for org, n in rows}


def _ago(t: float, now: float) -> str:
    days = int((now - t) // DAY)
    return "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"


def summarize(st: OrgState, accounts: int, now: float | None = None) -> CollegeSummary:
    now = now or time.time()
    c, tt, s = st.college, st.timetable, settings(st.id)
    ready = sum(1 for d in c.departments if c.department_status.get(d.id) and c.department_status[d.id].ready)
    stale = tt is not None and tt.college_revision != c.revision
    published = st.published.published_at if st.published else None
    if not c.departments:
        stage = "Setting up"
    elif tt is None:
        stage = "Ready to generate" if c.allotments and ready == len(c.departments) else "Collecting data"
    elif stale:
        stage = "Out of date"
    elif tt.published_at:
        stage = "Live"
    else:
        stage = "Draft"
    marked = len(attendance._all(st.id))
    upcoming = sum(1 for b in bookings._load(st.id)[1].values() if b.status == "booked")
    last = max([st.created_at, published or 0.0] + [a.at for a in st.audit[-1:]]
               + [x.at for x in c.department_status.values() if x.at])

    flags: list[str] = []
    warn = False
    if s.status == "paused":
        flags.append("Paused: members can't open the college.")
    elif s.status == "read_only":
        flags.append("Read-only: members can view but not change anything.")
    if stage == "Setting up" and now - st.created_at > DAY:
        flags.append(f"Signed up {_ago(st.created_at, now)} but hasn't started the setup.")
        warn = True
    if stage == "Collecting data" and c.departments:
        flags.append(f"{ready} of {len(c.departments)} departments Ready.")
        warn = warn or now - st.created_at > 3 * DAY
    if stage == "Ready to generate":
        flags.append("Every department is Ready: the timetable hasn't been generated yet.")
        warn = True
    if stage == "Draft" and st.audit and now - st.audit[-1].at > 2 * DAY:
        flags.append(f"A draft has waited to be published since {_ago(st.audit[-1].at, now)}.")
        warn = True
    if stage == "Out of date":
        flags.append("College data changed after the timetable was made: it needs regenerating.")
        warn = True
    if stage == "Live" and marked == 0:
        flags.append("Live, but no attendance marked yet (adoption).")
    if now - last > 7 * DAY and s.status == "active":
        flags.append(f"No activity since {_ago(last, now)}.")
        warn = True
    return CollegeSummary(
        id=st.id, name=st.name, is_demo=st.is_demo, created_at=st.created_at, plan=s.plan, status=s.status,
        note=s.note, stage=stage, departments=len(c.departments), departments_ready=ready, sections=len(c.sections),
        teachers=len(c.teachers), students=len(c.students), accounts=accounts, classes=len(tt.sessions) if tt else 0,
        published_at=published, attendance_marked=marked, bookings=upcoming, last_activity=last, flags=flags,
        needs_attention=warn)


def overview() -> PlatformOverview:
    accounts = _accounts()
    now = time.time()
    items = [summarize(st, accounts.get(oid, 0), now) for oid in store.org_ids() if (st := store.org(oid))]
    items.sort(key=lambda x: (not x.needs_attention, -x.last_activity))
    plans: dict[str, int] = {}
    for x in items:
        plans[x.plan] = plans.get(x.plan, 0) + 1
    return PlatformOverview(
        colleges=len(items), live=sum(x.stage == "Live" for x in items),
        needs_attention=sum(x.needs_attention for x in items), students=sum(x.students for x in items),
        teachers=sum(x.teachers for x in items), sections=sum(x.sections for x in items),
        classes=sum(x.classes for x in items), accounts=sum(x.accounts for x in items),
        attendance_marked=sum(x.attendance_marked for x in items), bookings=sum(x.bookings for x in items),
        plans=plans, items=items)


def seed_owner(password_hash: str) -> None:
    """The demo platform owner account (no college membership), when DEMO_PLATFORM_OWNER is on."""
    if not DEMO_PLATFORM_OWNER:
        return
    with SessionLocal() as db:
        if db.scalar(select(UserRow.id).where(UserRow.email == DEMO_OWNER_EMAIL)) is None:
            db.add(UserRow(email=DEMO_OWNER_EMAIL, name="Platform owner", password_hash=password_hash))
            db.commit()
