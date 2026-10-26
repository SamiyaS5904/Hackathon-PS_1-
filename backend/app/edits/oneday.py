"""One-day changes: cancel or move a class on a real date, leaving the weekly plan as it is.

The effective timetable for a date = weekly template for that weekday
- classes cancelled or moved away that date + classes moved onto that date.
A one-day move only uses free slots: nothing else is reshuffled for a single day.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from pydantic import BaseModel

from app import lunch
from app.edits.moves import MoveOption, check_slot
from app.models.domain import College, Override, Session, Timetable
from app.validator.check import validate

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Occurrence(BaseModel):
    """A class on a real date, as students will see it."""

    session: Session  # placement on this date (day = that date's weekday)
    date: str
    status: str  # "normal" | "cancelled" | "moved_out" | "moved_in"
    override_id: str | None = None
    note: str = ""
    # Stable id of this class on its original date: "<session id>@<YYYY-MM-DD>". A class moved to another
    # day keeps the id of the date it was moved from, so future attendance always hooks onto the same id.
    occurrence_id: str = ""
    substitute_for: str | None = None  # the usual teacher's id when a substitute takes this class


class DayInfo(BaseModel):
    date: str
    day: str
    label: str  # "Thu 23 Oct"
    working: bool
    holiday: str | None = None  # holiday name: no classes that day


def weekday(college: College, d: str) -> str | None:
    name = WEEKDAYS[date.fromisoformat(d).weekday()]
    return name if name in college.days else None


def label(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{WEEKDAYS[x.weekday()]} {x.day} {x.strftime('%b')}"


def week(college: College, start: str) -> list[DayInfo]:
    """The 7 dates of the week containing ``start`` (Monday first)."""
    d0 = date.fromisoformat(start)
    monday = d0 - timedelta(days=d0.weekday())
    out = []
    for i in range(7):
        d = (monday + timedelta(days=i)).isoformat()
        wd = WEEKDAYS[i]
        if wd in college.days:
            hol = next((h.label for h in college.holidays if h.date == d), None)
            out.append(DayInfo(date=d, day=wd, label=label(d), working=hol is None, holiday=hol))
    return out


def _placed(college: College, s: Session, day: str, p: int, venue_id: str) -> Session:
    shift = college.shift(s.shift_id)
    return s.model_copy(update={
        "day": day, "start_period": p, "venue_id": venue_id,
        "start": shift.periods[p].start, "end": shift.periods[p + s.length - 1].end,
    })


def occurrences(college: College, tt: Timetable, d: str) -> list[Occurrence]:
    if any(h.date == d for h in college.holidays):
        return []  # holiday: no classes (one-day moves onto it are refused)
    wd = weekday(college, d)
    by_id = {s.id: s for s in tt.sessions}
    out: list[Occurrence] = []
    if wd:
        away = {o.session_id: o for o in tt.overrides if o.date == d}
        for s in tt.sessions:
            if s.day != wd:
                continue
            o = away.get(s.id)
            if o is None:
                out.append(Occurrence(session=s, date=d, status="normal", occurrence_id=f"{s.id}@{d}"))
            elif o.kind == "cancel":
                out.append(Occurrence(session=s, date=d, status="cancelled", override_id=o.id, occurrence_id=f"{s.id}@{d}",
                                      note=o.reason or "Cancelled for this day"))
            elif o.kind == "substitute":
                # Happens as usual with another teacher: it counts as a normal class for clashes and lists.
                sub = college.teacher(o.teacher_id)
                out.append(Occurrence(session=s.model_copy(update={"teacher_id": o.teacher_id}), date=d,
                                      status="normal", override_id=o.id, occurrence_id=f"{s.id}@{d}",
                                      substitute_for=s.teacher_id,
                                      note=f"Substitute: {sub.name}"
                                      + (f" (for {college.teacher(s.teacher_id).name})" if s.teacher_id else "")))
            else:
                target = college.shift(s.shift_id).periods[o.start_period].start
                out.append(Occurrence(session=s, date=d, status="moved_out", override_id=o.id, occurrence_id=f"{s.id}@{d}",
                                      note=f"Moved to {label(o.to_date)} {target}"))
    for o in tt.overrides:
        if o.kind == "move" and o.to_date == d and o.session_id in by_id:
            twd = weekday(college, d)
            if twd is None:
                continue
            s = _placed(college, by_id[o.session_id], twd, o.start_period, o.venue_id)
            out.append(Occurrence(session=s, date=d, status="moved_in", override_id=o.id,
                                  occurrence_id=f"{o.session_id}@{o.date}",
                                  note=f"Moved from {label(o.date)} {by_id[o.session_id].start}"
                                  + (f" · {o.reason}" if o.reason else "")))
    return out


def active(college: College, tt: Timetable, d: str) -> list[Session]:
    return [o.session for o in occurrences(college, tt, d) if o.status in ("normal", "moved_in")]


def _day(college: College, tt: Timetable, d: str) -> tuple[list[Session], list]:
    """What happens on date ``d`` and that day's lunches (re-picked from what is free that day)."""
    sessions = active(college, tt, d)
    wd = weekday(college, d)
    return sessions, (lunch.for_day(college, sessions, wd, tt.lunches) if wd else [])


def day_options(college: College, tt: Timetable, session_id: str, from_date: str, to_date: str) -> list[MoveOption]:
    """Free slots on ``to_date`` for moving one occurrence. Anything that would disturb others is blocked."""
    s = next(x for x in tt.sessions if x.id == session_id)
    wd = weekday(college, to_date)
    if wd is None or any(h.date == to_date for h in college.holidays):
        return []
    # On its own date the class may move anywhere free; on another date its regular weekly occurrence
    # there is a separate class that really happens, so it counts like any other.
    others = [x for x in active(college, tt, to_date) if not (x.id == s.id and to_date == from_date)]
    out = []
    for p in range(len(college.shift(s.shift_id).periods)):
        if to_date == from_date and p == s.start_period:
            continue
        # A one-off change (moved class or makeup) may share a day with another lecture of the same subject:
        # "once a day" is a rule for the weekly plan, and makeup classes routinely double up.
        opt = check_slot(college, s, wd, p, others, tt.lunches, same_day_ok=True)
        if opt is None:
            continue
        if opt.status == "repair":  # one-day changes never reshuffle other classes
            opt.status = "blocked"
            opt.reason = opt.reason.replace("; those would be rearranged.", ".") or "Not free that day."
        out.append(opt)
    return out


def add_override(
    college: College, tt: Timetable, session_id: str, d: str, kind: str, to_date: str | None,
    start_period: int | None, reason: str, actor: str, teacher_id: str | None = None,
) -> tuple[Timetable | None, str, str]:
    """Returns (new timetable, message for the user, audit sentence) or (None, error, "").
    kind="substitute" needs ``teacher_id``: the teacher who takes the class that day."""
    s = next((x for x in tt.sessions if x.id == session_id), None)
    if s is None:
        return None, "Class not found.", ""
    if weekday(college, d) != s.day:
        return None, f"{college.subject(s.subject_id).name} doesn't happen on {label(d)}.", ""
    existing = next((o for o in tt.overrides if o.session_id == session_id and o.date == d), None)
    if existing is not None:
        if not (kind == "move" and existing.kind == "cancel"):
            return None, "This class already has a change for that day. Restore it first.", ""
        # A makeup class for a cancelled one: the move replaces the cancellation.
        tt = tt.model_copy(update={"overrides": [o for o in tt.overrides if o.id != existing.id]})

    subj = college.subject(s.subject_id).name
    secs = " + ".join(college.section(i).name for i in s.section_ids)
    if kind == "cancel":
        ov = Override(id=uuid.uuid4().hex[:10], session_id=s.id, date=d, kind="cancel", reason=reason,
                      created_by=actor)
        new = tt.model_copy(update={"overrides": [*tt.overrides, ov]})
        return (new, f"{subj} is cancelled on {label(d)} only. The weekly plan is unchanged.",
                f"Cancelled {subj} ({secs}) on {label(d)}")

    if kind == "substitute":
        sub = next((t for t in college.teachers if t.id == teacher_id), None)
        if sub is None or teacher_id == s.teacher_id:
            return None, "Choose another teacher to take this class.", ""
        ov = Override(id=uuid.uuid4().hex[:10], session_id=s.id, date=d, kind="substitute", teacher_id=sub.id,
                      reason=reason, created_by=actor)
        new = tt.model_copy(update={"overrides": [*tt.overrides, ov]})
        # The substitute must be free then, allowed in that shift, not blocked and within their daily limit.
        if validate(college, *_day(college, new, d), check_counts=False):
            return None, f"{sub.name} isn't free for this class on {label(d)}.", ""
        return (new, f"{sub.name} takes {subj} ({secs}) on {label(d)} {s.start}, this one time.",
                f"{sub.name} substitutes: {subj} ({secs}) on {label(d)}")

    if s.elective_slot_id:
        return None, "Elective groups meet together, so one group can't be moved on its own. Cancel it instead.", ""
    if kind != "move" or to_date is None or start_period is None:
        return None, "Choose a day and time to move the class to.", ""
    opt = next((o for o in day_options(college, tt, session_id, d, to_date) if o.start_period == start_period), None)
    if opt is None or opt.status != "free":
        return None, (opt.reason if opt else "That time isn't available."), ""
    ov = Override(id=uuid.uuid4().hex[:10], session_id=s.id, date=d, kind="move", to_date=to_date,
                  start_period=start_period, venue_id=opt.venue_id, reason=reason, created_by=actor)
    new = tt.model_copy(update={"overrides": [*tt.overrides, ov]})
    # Golden rule #1 on the real day: nothing on that date may clash, and every section still gets lunch.
    if validate(college, *_day(college, new, to_date), check_counts=False):
        return None, "That change would create a clash on that day.", ""
    when = f"{label(to_date)} {opt.start}"
    room = college.venue(opt.venue_id).name
    return (new, f"{subj} moves from {label(d)} {s.start} to {when} in {room}, this one time. "
            "The weekly plan is unchanged.",
            f"Moved {subj} ({secs}) from {label(d)} {s.start} to {when} (one day)")


def remove_override(college: College, tt: Timetable, override_id: str) -> tuple[Timetable | None, str]:
    ov = next((o for o in tt.overrides if o.id == override_id), None)
    if ov is None:
        return None, "That change no longer exists."
    s = next(x for x in tt.sessions if x.id == ov.session_id)
    new = tt.model_copy(update={"overrides": [o for o in tt.overrides if o.id != override_id]})
    if validate(college, *_day(college, new, ov.date), check_counts=False):
        return None, "Restoring would clash with another change made that day."
    subj = college.subject(s.subject_id).name
    return new, f"Restored {subj} on {label(ov.date)} to its usual time"


class MakeupOption(BaseModel):
    date: str
    label: str  # "Fri 30 Oct"
    start_period: int
    start: str
    end: str
    venue_id: str | None
    venue: str


def makeup_options(college: College, tt: Timetable, session_id: str, from_date: str, today: str,
                   days: int = 7, limit: int = 12) -> list[MakeupOption]:
    """Times in the coming days when the teacher, every student of the class and a suitable room are free
    (and lunch stays free): candidates for a makeup class. Soonest first; holidays and past dates skipped."""
    start = max(date.fromisoformat(from_date), date.fromisoformat(today))
    venues = {v.id: v.name for v in college.venues}
    out: list[MakeupOption] = []
    for i in range(days + 1):
        d = (start + timedelta(days=i)).isoformat()
        if weekday(college, d) is None or any(h.date == d for h in college.holidays):
            continue
        for o in day_options(college, tt, session_id, from_date, d):
            if o.status != "free" or (d == from_date and d < today):
                continue
            out.append(MakeupOption(date=d, label=label(d), start_period=o.start_period, start=o.start, end=o.end,
                                    venue_id=o.venue_id, venue=venues.get(o.venue_id or "", "")))
            if len(out) >= limit:
                return out
    return out
