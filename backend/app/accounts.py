"""Users, memberships (role per college) and invite links.

Roles: admin (College Admin) | coordinator (Department Coordinator) | teacher | student.
A membership may point to the college's own records: department_id (coordinator),
teacher_id (teacher), section_id + batch_id (student).
"""

from __future__ import annotations

import re
import secrets
import threading
import time

from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import DEMO_PASSWORD
from app.core.security import hash_password, verify_password
from app.db.models import InviteRow, MembershipRow, SessionLocal, UserRow, new_id
from app.models.domain import College
from app.seed.demo_college import build_demo_college
from app.store import store

ROLES = ("admin", "coordinator", "teacher", "student")


class Member(BaseModel):
    user_id: str
    org_id: str
    org_name: str
    name: str
    email: str
    role: str
    department_id: str | None = None
    teacher_id: str | None = None
    section_id: str | None = None
    batch_id: str | None = None


class InviteOut(BaseModel):
    token: str
    org_id: str
    org_name: str
    email: str
    role: str
    department_id: str | None
    teacher_id: str | None
    status: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def find_user(email: str) -> UserRow | None:
    with SessionLocal() as db:
        return db.scalar(select(UserRow).where(UserRow.email == normalize_email(email)))


# ---- cache --------------------------------------------------------------------
# Every request checks who is calling and their role in the college. With a remote database
# each lookup is a network round trip, so users and their memberships are kept in memory.
# Every write in this module clears the cache; the TTL covers writes from another process.
_CACHE_TTL = 60.0
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, UserRow | None, list[MembershipRow]]] = {}


def _forget() -> None:
    with _cache_lock:
        _cache.clear()


def _user_and_rows(user_id: str) -> tuple[UserRow | None, list[MembershipRow]]:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(user_id)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1], hit[2]
    with SessionLocal() as db:
        user = db.get(UserRow, user_id)
        rows = list(db.scalars(select(MembershipRow).where(MembershipRow.user_id == user_id))) if user else []
    with _cache_lock:
        _cache[user_id] = (now, user, rows)
    return user, rows


def get_user(user_id: str) -> UserRow | None:
    return _user_and_rows(user_id)[0]


def create_user(email: str, name: str, password: str) -> UserRow:
    with SessionLocal() as db:
        user = UserRow(email=normalize_email(email), name=name.strip(), password_hash=hash_password(password))
        db.add(user)
        db.commit()
    _forget()
    return user


def authenticate(email: str, password: str) -> UserRow | None:
    user = find_user(email)
    if user is None:
        return _first_student_login(email, password)
    return user if verify_password(password, user.password_hash) else None


def _first_student_login(email: str, password: str) -> UserRow | None:
    """Students from an uploaded list log in with their email; the first password is their roll number.

    The account is created on that first login, so importing hundreds of students stays instant.
    """
    email = normalize_email(email)
    for org_id in store.org_ids():
        college = store.org(org_id).college
        st = next((s for s in college.students if s.email.lower() == email), None)
        if st and password.strip().lower() == st.roll_no.lower():
            with SessionLocal() as db:
                user = UserRow(email=email, name=st.name, password_hash=hash_password(password.strip()))
                db.add(user)
                db.flush()
                db.add(MembershipRow(user_id=user.id, org_id=org_id, role="student", section_id=st.section_id,
                                     batch_id=st.batch_id))
                db.commit()
            _forget()
            return user
    return None


def _member(row: MembershipRow, user: UserRow) -> Member:
    org = store.org(row.org_id)
    return Member(user_id=user.id, org_id=row.org_id, org_name=org.name if org else row.org_id, name=user.name,
                  email=user.email, role=row.role, department_id=row.department_id, teacher_id=row.teacher_id,
                  section_id=row.section_id, batch_id=row.batch_id)


def memberships(user_id: str) -> list[Member]:
    user, rows = _user_and_rows(user_id)
    return [_member(r, user) for r in rows if store.org(r.org_id)] if user else []


def membership(user_id: str, org_id: str) -> Member | None:
    user, rows = _user_and_rows(user_id)
    row = next((r for r in rows if r.org_id == org_id), None)
    return _member(row, user) if row and user else None


def add_membership(user_id: str, org_id: str, role: str, **links: str | None) -> None:
    with SessionLocal() as db:
        db.add(MembershipRow(user_id=user_id, org_id=org_id, role=role, **links))
        db.commit()
    _forget()


def list_members(org_id: str) -> list[Member]:
    with SessionLocal() as db:
        rows = db.execute(
            select(MembershipRow, UserRow).join(UserRow, UserRow.id == MembershipRow.user_id)
            .where(MembershipRow.org_id == org_id, MembershipRow.role != "student")
        ).all()
        return sorted((_member(m, u) for m, u in rows), key=lambda m: (ROLES.index(m.role), m.name))


def count_students(org_id: str) -> int:
    with SessionLocal() as db:
        return len(db.scalars(select(MembershipRow.id).where(MembershipRow.org_id == org_id,
                                                             MembershipRow.role == "student")).all())


# ---- invites ------------------------------------------------------------

def create_invite(org_id: str, email: str, role: str, created_by: str, department_id: str | None = None,
                  teacher_id: str | None = None) -> InviteOut:
    with SessionLocal() as db:
        row = InviteRow(org_id=org_id, token=secrets.token_urlsafe(24), email=normalize_email(email), role=role,
                        department_id=department_id, teacher_id=teacher_id, created_by=created_by)
        db.add(row)
        db.commit()
        return _invite_out(row)


def _invite_out(row: InviteRow) -> InviteOut:
    org = store.org(row.org_id)
    return InviteOut(token=row.token, org_id=row.org_id, org_name=org.name if org else row.org_id, email=row.email,
                     role=row.role, department_id=row.department_id, teacher_id=row.teacher_id, status=row.status)


def get_invite(token: str) -> InviteOut | None:
    with SessionLocal() as db:
        row = db.scalar(select(InviteRow).where(InviteRow.token == token))
        return _invite_out(row) if row else None


def list_invites(org_id: str) -> list[InviteOut]:
    with SessionLocal() as db:
        rows = db.scalars(select(InviteRow).where(InviteRow.org_id == org_id, InviteRow.status == "pending")
                          .order_by(InviteRow.created_at.desc())).all()
        return [_invite_out(r) for r in rows]


def accept_invite(token: str, name: str, password: str) -> tuple[UserRow | None, str]:
    """Create (or reuse) the account for the invited email and add the membership."""
    with SessionLocal() as db:
        inv = db.scalar(select(InviteRow).where(InviteRow.token == token))
        if inv is None or inv.status != "pending":
            return None, "This invite link is no longer valid."
        user = db.scalar(select(UserRow).where(UserRow.email == inv.email))
        if user is None:
            if len(password) < 8:
                return None, "Choose a password with at least 8 characters."
            user = UserRow(email=inv.email, name=name.strip() or inv.email, password_hash=hash_password(password))
            db.add(user)
            db.flush()
        elif not verify_password(password, user.password_hash):
            return None, "An account with this email already exists: enter its password to join."
        exists = db.scalar(select(MembershipRow).where(MembershipRow.user_id == user.id,
                                                       MembershipRow.org_id == inv.org_id))
        if exists is None:
            db.add(MembershipRow(user_id=user.id, org_id=inv.org_id, role=inv.role,
                                 department_id=inv.department_id, teacher_id=inv.teacher_id))
        inv.status = "accepted"
        db.commit()
    _forget()
    return user, ""


# ---- demo college ----------------------------------------------------------

def _slug_email(name: str, domain: str, used: set[str]) -> str:
    base = re.sub(r"^(dr|prof)\.?\s+", "", name.strip(), flags=re.I)
    base = re.sub(r"[^a-z0-9]+", ".", base.lower()).strip(".")
    email, n = f"{base}@{domain}", 2
    while email in used:
        email, n = f"{base}{n}@{domain}", n + 1
    used.add(email)
    return email


def seed_demo() -> None:
    """Create the demo college with ready-made accounts (once). Every demo account uses DEMO_PASSWORD."""
    if store.org("demo") is None:
        store.create_org("Demo Institute of Technology", build_demo_college(), is_demo=True, slug="demo")
    with SessionLocal() as db:  # a first start that was stopped half-way left the college without accounts
        has_accounts = db.scalar(select(MembershipRow.id).where(MembershipRow.org_id == "demo").limit(1))
    if not has_accounts:
        seed_accounts("demo", store.org("demo").college, "demo.timetabl.ai")


def seed_accounts(org_id: str, college: College, domain: str) -> None:
    shared_hash = hash_password(DEMO_PASSWORD)  # one hash for all demo accounts keeps seeding fast
    used: set[str] = set()
    accounts: list[tuple[str, str, str, dict]] = [(f"admin@{domain}", "College Admin", "admin", {})]
    used.add(f"admin@{domain}")
    for d in college.departments:
        email = f"{d.id}.coordinator@{domain}"
        used.add(email)
        accounts.append((email, f"{d.short} Coordinator", "coordinator", {"department_id": d.id}))
    for t in college.teachers:
        accounts.append((_slug_email(t.name, domain, used), t.name, "teacher",
                         {"department_id": t.department_id, "teacher_id": t.id}))
    for st in college.students:
        accounts.append((st.email, st.name, "student", {"section_id": st.section_id, "batch_id": st.batch_id}))

    with SessionLocal() as db:
        # One lookup per 500 emails and one batched insert: a remote database (Supabase) costs a round
        # trip per statement, and a college can have thousands of students.
        emails = [a[0] for a in accounts]
        existing: dict[str, UserRow] = {}
        for i in range(0, len(emails), 500):
            chunk = emails[i:i + 500]
            existing.update({u.email: u for u in db.scalars(select(UserRow).where(UserRow.email.in_(chunk)))})
        new_users = []
        for email, name, *_ in accounts:
            if email not in existing:
                existing[email] = UserRow(id=new_id(), email=email, name=name, password_hash=shared_hash)
                new_users.append(existing[email])
        db.add_all(new_users)
        db.flush()  # users before memberships: the foreign key needs them first
        db.add_all([MembershipRow(id=new_id(), user_id=existing[email].id, org_id=org_id, role=role, **links)
                    for email, _, role, links in accounts])
        db.commit()
    _forget()
