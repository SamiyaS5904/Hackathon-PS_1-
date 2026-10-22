"""In-app notifications.

A notification is stored once with an *audience* (everyone, roles, sections, elective group
members, teachers, department Coordinators) and matched against each member when they read
their feed. Read state is one "seen up to" time per user and college.

Changes only notify once the timetable is published: drafts are invisible to teachers and
students, so telling them about a draft would confuse them.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.accounts import Member
from app.db.models import NotificationRow, NotificationSeenRow, SessionLocal
from app.models.domain import College, Session, Timetable

FEED_SIZE = 30


class Audience(BaseModel):
    everyone: bool = False
    roles: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(default_factory=list)  # students of these sections
    student_emails: list[str] = Field(default_factory=list)  # e.g. members of an elective group
    teacher_ids: list[str] = Field(default_factory=list)
    coordinator_departments: list[str] = Field(default_factory=list)

    def empty(self) -> bool:
        return not (self.everyone or self.roles or self.section_ids or self.student_emails or self.teacher_ids
                    or self.coordinator_departments)


class NotificationOut(BaseModel):
    id: str
    at: float
    title: str
    body: str
    link: str
    unread: bool


class FeedOut(BaseModel):
    items: list[NotificationOut]
    unread: int


def matches(a: Audience, m: Member) -> bool:
    if a.everyone or m.role in a.roles:
        return True
    if m.role == "student":
        return m.section_id in a.section_ids or m.email in a.student_emails
    if m.role == "teacher":
        return m.teacher_id in a.teacher_ids
    if m.role == "coordinator":
        return m.department_id in a.coordinator_departments
    return False


def send(org: str, title: str, body: str, audience: Audience, actor_user_id: str = "", link: str = "/timetable",
         ) -> None:
    if audience.empty():
        return
    with SessionLocal() as db:
        db.add(NotificationRow(org_id=org, at=time.time(), title=title[:300], body=body[:1000], link=link,
                               audience=audience.model_dump(), actor_user_id=actor_user_id))
        db.commit()


def feed(m: Member) -> FeedOut:
    with SessionLocal() as db:
        seen = db.get(NotificationSeenRow, (m.user_id, m.org_id))
        seen_at = seen.seen_at if seen else 0.0
        rows = db.scalars(select(NotificationRow).where(NotificationRow.org_id == m.org_id)
                          .order_by(NotificationRow.at.desc()).limit(500)).all()
    mine = [r for r in rows if r.actor_user_id != m.user_id and matches(Audience.model_validate(r.audience), m)]
    items = [NotificationOut(id=r.id, at=r.at, title=r.title, body=r.body, link=r.link, unread=r.at > seen_at)
             for r in mine[:FEED_SIZE]]
    return FeedOut(items=items, unread=sum(1 for r in mine if r.at > seen_at))


def mark_seen(m: Member) -> None:
    with SessionLocal() as db:
        row = db.get(NotificationSeenRow, (m.user_id, m.org_id))
        if row is None:
            db.add(NotificationSeenRow(user_id=m.user_id, org_id=m.org_id, seen_at=time.time()))
        else:
            row.seen_at = time.time()
        db.commit()


# ---- who a change concerns ---------------------------------------------------

def session_audience(college: College, sessions: list[Session]) -> Audience:
    """Students, teacher and department Coordinators of these classes, plus the Coordinator of any
    department whose room they borrow (owner notified, first-come rooms)."""
    a = Audience()
    for s in sessions:
        if s.elective_slot_id:
            group = college.elective_group(s.elective_slot_id, s.group_id)
            emails = {st.id: st.email for st in college.students}
            a.student_emails += [emails[i] for i in group.student_ids if emails.get(i)]
        else:
            a.section_ids += s.section_ids
        if s.teacher_id:
            a.teacher_ids.append(s.teacher_id)
        a.coordinator_departments += [college.section(i).department_id for i in s.section_ids]
        venue_dept = college.venue(s.venue_id).department_id
        if venue_dept:
            a.coordinator_departments.append(venue_dept)
    for key in ("section_ids", "student_emails", "teacher_ids", "coordinator_departments"):
        setattr(a, key, sorted(set(getattr(a, key))))
    return a


def changed_sessions(before: Timetable | None, after: Timetable) -> list[Session]:
    """Classes whose weekly slot, room or teacher differ, or whose one-day changes were added or removed
    (both the old and the new version, so everyone who had or gets the class hears about it)."""
    if before is None:
        return []
    old = {s.id: s for s in before.sessions}
    new = {s.id: s for s in after.sessions}
    out: dict[str, Session] = {}
    for sid, s in new.items():
        o = old.get(sid)
        if o is None or (o.day, o.start_period, o.venue_id, o.teacher_id) != (s.day, s.start_period, s.venue_id,
                                                                              s.teacher_id):
            out[sid] = s
            if o is not None:
                out[sid + "@old"] = o
    ov_before = {o.id: o.session_id for o in before.overrides}
    ov_after = {o.id: o.session_id for o in after.overrides}
    for oid in set(ov_before) ^ set(ov_after):
        sid = ov_after.get(oid) or ov_before.get(oid)
        if sid in new:
            out.setdefault(sid, new[sid])
    return list(out.values())


def notify_change(org: str, college: College, before: Timetable | None, after: Timetable, title: str, body: str,
                  actor_user_id: str, skip_teacher: str | None = None) -> None:
    """``skip_teacher``: already told separately (e.g. their own request was approved)."""
    if not after.published_at:
        return
    audience = session_audience(college, changed_sessions(before, after))
    audience.teacher_ids = [t for t in audience.teacher_ids if t != skip_teacher]
    send(org, title, body, audience, actor_user_id)
