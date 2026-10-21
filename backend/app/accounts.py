"""Users, memberships (role per college) and invite links.

Roles: admin (College Admin) | coordinator (Department Coordinator) | teacher | student.
A membership may point to the college's own records: department_id (coordinator),
teacher_id (teacher), section_id + batch_id (student).
"""

from __future__ import annotations

import re
import secrets

from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import DEMO_PASSWORD
from app.core.security import hash_password, verify_password
from app.db.models import InviteRow, MembershipRow, SessionLocal, UserRow
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


def get_user(user_id: str) -> UserRow | None:
    with SessionLocal() as db:
        return db.get(UserRow, user_id)


def create_user(email: str, name: str, password: str) -> UserRow:
    with SessionLocal() as db:
        user = UserRow(email=normalize_email(email), name=name.strip(), password_hash=hash_password(password))
        db.add(user)
        db.commit()
        return user


def authenticate(email: str, password: str) -> UserRow | None:
    user = find_user(email)
    return user if user and verify_password(password, user.password_hash) else None


def _member(row: MembershipRow, user: UserRow) -> Member:
    org = store.org(row.org_id)
    return Member(user_id=user.id, org_id=row.org_id, org_name=org.name if org else row.org_id, name=user.name,
                  email=user.email, role=row.role, department_id=row.department_id, teacher_id=row.teacher_id,
                  section_id=row.section_id, batch_id=row.batch_id)


def memberships(user_id: str) -> list[Member]:
    with SessionLocal() as db:
        user = db.get(UserRow, user_id)
        rows = db.scalars(select(MembershipRow).where(MembershipRow.user_id == user_id)).all()
        return [_member(r, user) for r in rows if store.org(r.org_id)]


def membership(user_id: str, org_id: str) -> Member | None:
    with SessionLocal() as db:
        row = db.scalar(select(MembershipRow).where(MembershipRow.user_id == user_id,
                                                    MembershipRow.org_id == org_id))
        return _member(row, db.get(UserRow, user_id)) if row else None


def add_membership(user_id: str, org_id: str, role: str, **links: str | None) -> None:
    with SessionLocal() as db:
        db.add(MembershipRow(user_id=user_id, org_id=org_id, role=role, **links))
        db.commit()


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
    if store.org("demo"):
        return
    college = build_demo_college()
    store.create_org("Demo Institute of Technology", college, is_demo=True, slug="demo")
    seed_accounts("demo", store.org("demo").college, "demo.timetabl.ai")


def seed_accounts(org_id: str, college: College, domain: str) -> None:
    shared_hash = hash_password(DEMO_PASSWORD)  # one hash for all demo accounts keeps seeding fast
    used: set[str] = set()
    with SessionLocal() as db:
        def add(email: str, name: str, role: str, **links: str | None) -> None:
            user = db.scalar(select(UserRow).where(UserRow.email == email))
            if user is None:
                user = UserRow(email=email, name=name, password_hash=shared_hash)
                db.add(user)
                db.flush()
            db.add(MembershipRow(user_id=user.id, org_id=org_id, role=role, **links))

        add(f"admin@{domain}", "College Admin", "admin")
        used.add(f"admin@{domain}")
        for d in college.departments:
            email = f"{d.id}.coordinator@{domain}"
            used.add(email)
            add(email, f"{d.short} Coordinator", "coordinator", department_id=d.id)
        for t in college.teachers:
            add(_slug_email(t.name, domain, used), t.name, "teacher", department_id=t.department_id,
                teacher_id=t.id)
        for s in college.students:
            add(s.email, s.name, "student", section_id=s.section_id, batch_id=s.batch_id)
        db.commit()
