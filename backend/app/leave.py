"""Teacher leave and its cover plan.

A leave is a teacher away on some dates: the teacher asks (the Department Coordinator approves) or the
Coordinator / College Admin enters it directly. For the classes it touches the system builds a **cover plan**:
each class gets a substitute (a teacher who teaches the same subject, or else a colleague of the same department,
free at that time, allowed in that shift, not blocked and within their daily limit) or is cancelled, chosen per
year. The plan is only a preview; applying it adds one-day changes (kind "substitute" / "cancel") that the
validator checks for every date, exactly like any other one-day change.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import LeaveRow, SessionLocal
from app.edits.oneday import _day, add_override, label, occurrences, weekday
from app.models.domain import College, Override, Session, Timetable
from app.validator.check import validate

MAX_DAYS = 14  # longest leave planned in one go (calendar days)
OPTIONS = 3  # substitutes shown per class


# ---- the leave record ------------------------------------------------------------

class LeaveOut(BaseModel):
    id: str
    at: float
    teacher_id: str
    teacher_name: str
    department_id: str
    start_date: str
    end_date: str
    reason: str = ""
    status: str  # pending | approved | declined | withdrawn
    requested_by: str = ""
    decided_by: str = ""
    decided_at: float | None = None
    note: str = ""
    applied_at: float | None = None  # when the cover plan was applied
    plan_summary: str = ""  # "4 classes covered, 2 cancelled"


def _out(r: LeaveRow) -> LeaveOut:
    return LeaveOut(id=r.id, at=r.at, teacher_id=r.teacher_id, status=r.status, **r.data)


def create(org: str, teacher_id: str, teacher_name: str, department_id: str, start_date: str, end_date: str,
           reason: str, requested_by: str, status: str = "pending", decided_by: str = "") -> LeaveOut:
    data = {"teacher_name": teacher_name, "department_id": department_id, "start_date": start_date,
            "end_date": end_date, "reason": reason[:500], "requested_by": requested_by, "decided_by": decided_by,
            "decided_at": time.time() if decided_by else None}
    with SessionLocal() as db:
        row = LeaveRow(org_id=org, at=time.time(), teacher_id=teacher_id, status=status, data=data)
        db.add(row)
        db.commit()
        return _out(row)


def get(org: str, leave_id: str) -> LeaveOut | None:
    with SessionLocal() as db:
        row = db.get(LeaveRow, leave_id)
        return _out(row) if row is not None and row.org_id == org else None


def listing(org: str, *, teacher_id: str | None = None, department_id: str | None = None) -> list[LeaveOut]:
    """Waiting first, then newest first."""
    with SessionLocal() as db:
        rows = db.scalars(select(LeaveRow).where(LeaveRow.org_id == org).order_by(LeaveRow.at.desc())
                          .limit(200)).all()
    out = [_out(r) for r in rows]
    if teacher_id is not None:
        out = [x for x in out if x.teacher_id == teacher_id]
    if department_id is not None:
        out = [x for x in out if x.department_id == department_id]
    return sorted(out, key=lambda x: x.status != "pending")


def update(org: str, leave_id: str, status: str | None = None, **fields) -> LeaveOut | None:
    with SessionLocal() as db:
        row = db.get(LeaveRow, leave_id)
        if row is None or row.org_id != org:
            return None
        if status is not None:
            row.status = status
        row.data = {**row.data, **fields}
        db.commit()
        return _out(row)


def working_dates(college: College, start: str, end: str) -> list[str]:
    """Teaching dates from ``start`` to ``end`` (inclusive): working weekdays that aren't holidays."""
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    if d1 < d0:
        raise ValueError("The last day of leave is before the first.")
    if (d1 - d0).days >= MAX_DAYS:
        raise ValueError(f"Plan at most {MAX_DAYS} days of leave at a time.")
    holidays = {h.date for h in college.holidays}
    out = []
    for i in range((d1 - d0).days + 1):
        d = (d0 + timedelta(days=i)).isoformat()
        if weekday(college, d) and d not in holidays:
            out.append(d)
    return out


# ---- the cover plan ----------------------------------------------------------------

class CoverOption(BaseModel):
    teacher_id: str
    name: str
    score: int
    why: str  # "Teaches DBMS · 2 other classes that day · covered 1 this month"


class PlanItem(BaseModel):
    session_id: str
    date: str
    day_label: str  # "Thu 30 Oct"
    start: str
    end: str
    subject: str
    sections: str  # "CSE-3A" / "CSE-3A + CSE-3B"
    year: int | None
    venue: str
    action: str  # "substitute" | "cancel"
    teacher_id: str | None = None  # the substitute
    teacher_name: str = ""
    options: list[CoverOption] = Field(default_factory=list)
    note: str = ""


class LeavePlan(BaseModel):
    teacher_id: str
    teacher_name: str
    start_date: str
    end_date: str
    dates: list[str]
    years: list[int]  # years whose classes are touched
    items: list[PlanItem]
    covered: int
    cancelled: int
    summary: str
    problems: list[str] = Field(default_factory=list)  # classes the plan leaves alone, with the reason


def _year(college: College, s: Session) -> int | None:
    return college.section(s.section_ids[0]).year if s.section_ids else None


def _who(college: College, s: Session) -> str:
    names = " + ".join(college.section(i).name for i in s.section_ids)
    batch = next((b.name for i in s.section_ids for b in college.section(i).batches if b.id == s.batch_id), None)
    return f"{names} ({batch})" if batch else names


def affected(college: College, tt: Timetable, teacher_id: str, dates: list[str]) -> tuple[list[tuple[str, Session]], list[str]]:
    """The teacher's classes on these dates (in date and time order), and notes on ones the plan can't touch."""
    out, skipped = [], []
    for d in dates:
        for o in sorted(occurrences(college, tt, d), key=lambda o: o.session.start):
            if o.session.teacher_id != teacher_id:
                continue
            if o.status == "normal" and o.override_id is None:
                out.append((d, o.session))
            elif o.status == "moved_in":
                subject = college.subject(o.session.subject_id).name
                skipped.append(f"{subject} on {label(d)} was moved to that day "
                               "earlier; change it from the Changes page.")
    return out, skipped


def _with(tt: Timetable, ov: Override) -> Timetable:
    return tt.model_copy(update={"overrides": [*tt.overrides, ov]})


def _covers_in_month(tt: Timetable, teacher_id: str, d: str) -> int:
    return sum(1 for o in tt.overrides if o.kind == "substitute" and o.teacher_id == teacher_id
               and o.date[:7] == d[:7])


def rank_substitutes(college: College, tt: Timetable, s: Session, d: str, away: set[str],
                     limit: int = OPTIONS) -> list[CoverOption]:
    """Who can take class ``s`` on date ``d``: same-subject teachers first, then colleagues of the class's
    department, each checked by the validator on that day. Fewer classes that day and fewer covers this
    month rank higher, so the extra work is shared fairly."""
    prefs = {(x.teacher_id, x.subject_id): x.preference for x in college.teacher_subjects}
    subject = college.subject(s.subject_id)
    depts = {college.section(i).department_id for i in s.section_ids}
    day = [x for x in occurrences(college, tt, d) if x.status in ("normal", "moved_in")]
    t0, t1 = s.start, s.end
    scored: list[tuple[int, str, CoverOption]] = []
    for t in college.teachers:
        if t.id in away or t.id == s.teacher_id or s.shift_id not in t.shift_ids:
            continue
        pref = prefs.get((t.id, s.subject_id))
        if pref is None and t.department_id not in depts:
            continue  # someone from another department who doesn't teach the subject: not a sensible cover
        mine = [x.session for x in day if x.session.teacher_id == t.id]
        if any(x.start < t1 and t0 < x.end for x in mine):
            continue  # busy then (the validator double-checks across shifts)
        load = sum(x.length for x in mine)
        if load + s.length > t.max_per_day:
            continue
        covers = _covers_in_month(tt, t.id, d)
        knows = any(set(x.section_ids) & set(s.section_ids) for x in (y.session for y in day) if x.teacher_id == t.id) \
            or any(x.teacher_id == t.id and set(x.section_ids) & set(s.section_ids) for x in tt.sessions)
        score = (60 if pref == 1 else 50 if pref is not None else 20) + (10 if knows else 0) - 6 * load - 4 * covers
        why = [f"Teaches {subject.name}" if pref is not None else "Same department, free then"]
        if knows:
            why.append("knows this class")
        why.append(f"{load} other period{'s' if load != 1 else ''} that day" if load else "free all day")
        if covers:
            why.append(f"covered {covers} this month")
        scored.append((score, t.name, CoverOption(teacher_id=t.id, name=t.name, score=score, why=" · ".join(why))))
    out = []
    for _, _, opt in sorted(scored, key=lambda x: (-x[0], x[1])):
        trial = _with(tt, Override(id="trial", session_id=s.id, date=d, kind="substitute", teacher_id=opt.teacher_id))
        if not validate(college, *_day(college, trial, d), check_counts=False):
            out.append(opt)
            if len(out) >= limit:
                break
    return out


def build_plan(college: College, tt: Timetable, teacher_id: str, start: str, end: str,
               actions: dict[int, str] | None = None, default: str = "substitute") -> LeavePlan:
    """Cover plan for a leave. ``actions``: per year "substitute" or "cancel" (others use ``default``).
    Substitutes picked earlier in the plan count as busy for later classes, so the plan never double-books."""
    actions = actions or {}
    teacher = college.teacher(teacher_id)
    dates = working_dates(college, start, end)
    classes, problems = affected(college, tt, teacher_id, dates)
    work = tt
    items: list[PlanItem] = []
    for d, s in classes:
        year = _year(college, s)
        want = actions.get(year, default) if year is not None else default
        opts = rank_substitutes(college, work, s, d, away={teacher_id})
        item = PlanItem(session_id=s.id, date=d, day_label=label(d), start=s.start, end=s.end,
                        subject=college.subject(s.subject_id).name,
                        sections=_who(college, s),
                        year=year, venue=college.venue(s.venue_id).name, action="cancel", options=opts)
        if want == "substitute":
            if opts:
                best = opts[0]
                item.action, item.teacher_id, item.teacher_name = "substitute", best.teacher_id, best.name
                work = _with(work, Override(id=f"plan{len(items)}", session_id=s.id, date=d, kind="substitute",
                                            teacher_id=best.teacher_id))
            else:
                item.note = "No free teacher who can take it, so it is cancelled."
        items.append(item)
    covered = sum(1 for i in items if i.action == "substitute")
    cancelled = len(items) - covered
    years = sorted({i.year for i in items if i.year is not None})
    if not items:
        summary = f"{teacher.name} has no classes on those days. Nothing to cover."
    else:
        summary = (f"{len(items)} class{'es' if len(items) != 1 else ''} of {teacher.name} on "
                   f"{len(dates)} day{'s' if len(dates) != 1 else ''}: {covered} covered by a substitute, "
                   f"{cancelled} cancelled.")
    return LeavePlan(teacher_id=teacher_id, teacher_name=teacher.name, start_date=start, end_date=end, dates=dates,
                     years=years, items=items, covered=covered, cancelled=cancelled, summary=summary,
                     problems=problems)


class CoverChoice(BaseModel):
    session_id: str
    date: str
    action: str  # "substitute" | "cancel"
    teacher_id: str | None = None


def apply_plan(college: College, tt: Timetable, teacher_id: str, choices: list[CoverChoice], reason: str,
               actor: str) -> tuple[Timetable | None, str, list[str]]:
    """All or nothing: (new timetable, "", audit sentences) or (None, what went wrong, [])."""
    away = college.teacher(teacher_id)
    note = f"{away.name} on leave" + (f": {reason}" if reason else "")
    actions = []
    for c in choices:
        s = next((x for x in tt.sessions if x.id == c.session_id), None)
        if s is None or s.teacher_id != teacher_id:
            return None, "One of these classes isn't this teacher's any more. Make the plan again.", []
        kind = "substitute" if c.action == "substitute" else "cancel"
        new, message, action = add_override(college, tt, c.session_id, c.date, kind, None, None, note, actor,
                                            teacher_id=c.teacher_id)
        if new is None:
            return None, f"{college.subject(s.subject_id).name} on {label(c.date)}: {message}", []
        tt = new
        actions.append(action)
    for d in sorted({c.date for c in choices}):
        if validate(college, *_day(college, tt, d), check_counts=False):
            return None, f"This plan would create a clash on {label(d)}. Make the plan again.", []
    return tt, "", actions
