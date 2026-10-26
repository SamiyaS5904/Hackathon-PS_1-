"""Database tables. Every tenant table carries ``org_id``; the backend only ever queries
within the org the logged-in user is a member of (root CLAUDE.md golden rule 5).

College data and timetables are stored as JSON documents (validated by the Pydantic
domain models on load), so the scheduling model can evolve without schema migrations.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import DATABASE_URL


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class Base(DeclarativeBase):
    pass


class OrgRow(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug, used in URLs
    name: Mapped[str] = mapped_column(String(200))
    college: Mapped[dict] = mapped_column(JSON)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class MembershipRow(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # admin | coordinator | teacher | student
    department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    teacher_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    section_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class InviteRow(Base):
    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    teacher_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | accepted | revoked
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class TimetableRow(Base):
    __tablename__ = "timetables"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class PublishedRow(Base):
    """The timetable teachers and students see while the Admin works on a newer draft."""

    __tablename__ = "published_timetables"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class AuditRow(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    at: Mapped[float] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(200))
    changes: Mapped[list] = mapped_column(JSON)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON)
    undone: Mapped[bool] = mapped_column(Boolean, default=False)


class ChangeRequestRow(Base):
    """A teacher's request to move one of their lectures permanently; the Coordinator decides."""

    __tablename__ = "change_requests"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    at: Mapped[float] = mapped_column(Float, default=time.time)
    user_id: Mapped[str] = mapped_column(String(32))
    teacher_name: Mapped[str] = mapped_column(String(200))
    teacher_id: Mapped[str] = mapped_column(String(64))
    department_ids: Mapped[list] = mapped_column(JSON)  # departments of the class's sections
    session_id: Mapped[str] = mapped_column(String(64))
    day: Mapped[str] = mapped_column(String(10))
    start_period: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(500))  # "Programming in C (CSE-1A): Mon 10:10 -> Thu 11:00"
    reason: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|declined|withdrawn
    decided_by: Mapped[str] = mapped_column(String(200), default="")
    decided_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(500), default="")


class AttendanceRow(Base):
    """Attendance for one class on one real date (``occurrence_id`` = "<session id>@<original date>").
    Stores who was absent; everyone else on that class's roster was present."""

    __tablename__ = "attendance"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    occurrence_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(64))
    date: Mapped[str] = mapped_column(String(10), index=True)
    roster: Mapped[list] = mapped_column(JSON)  # student ids expected in class
    absent: Mapped[list] = mapped_column(JSON)
    marked_by: Mapped[str] = mapped_column(String(200))
    marked_at: Mapped[float] = mapped_column(Float)


class NotificationRow(Base):
    """One in-app notification for an audience (sections, teachers, departments, roles), not a user list,
    so students who log in later still see what concerns them."""

    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(String(1000), default="")
    link: Mapped[str] = mapped_column(String(200), default="/timetable")
    audience: Mapped[dict] = mapped_column(JSON)
    actor_user_id: Mapped[str] = mapped_column(String(32), default="")


class NotificationSeenRow(Base):
    __tablename__ = "notifications_seen"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    seen_at: Mapped[float] = mapped_column(Float, default=0.0)


class PlatformOrgRow(Base):
    """Platform-level settings of one college, kept by the platform owner: plan and status.
    Separate from the college's own data, which the platform owner never edits."""

    __tablename__ = "platform_orgs"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    plan: Mapped[str] = mapped_column(String(20), default="trial")  # trial | pro | campus
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | read_only | paused
    note: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_by: Mapped[str] = mapped_column(String(200), default="")


class BookingRow(Base):
    """Teacher booking: a teacher's weekly office hour (kind "office_hour") or a booked doubt slot /
    meeting on a real date (kind "booking"). The fields live in ``data`` (see app/bookings.py)."""

    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSON)


class LeaveRow(Base):
    """A teacher's leave (dates + reason), asked by the teacher or entered by the Coordinator / Admin.
    The other fields live in ``data`` (see app/leave.py)."""

    __tablename__ = "leaves"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    at: Mapped[float] = mapped_column(Float, default=time.time)
    teacher_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|declined|withdrawn
    data: Mapped[dict] = mapped_column(JSON)


_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# Postgres: requests rarely touch the database (memory first, background writer), so a liveness
# ping per checkout is cheap; TCP keepalives stop idle Supabase connections from silently dying.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args=_connect_args)
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, pool_size=5, max_overflow=5,
                           connect_args={"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10,
                                         "keepalives_count": 3, "connect_timeout": 15})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
