"""One-day changes: cancel or move a class on a real date, leaving the weekly plan as it is.

The effective timetable for a date = weekly template for that weekday
- classes cancelled or moved away that date + classes moved onto that date.
A one-day move only uses free slots: nothing else is reshuffled for a single day.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from pydantic import BaseModel

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


class DayInfo(BaseModel):
    date: str
    day: str
    label: str  # "Thu 23 Oct"
    working: bool


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
            out.append(DayInfo(date=d, day=wd, label=label(d), working=True))
    return out


def _placed(college: College, s: Session, day: str, p: int, venue_id: str) -> Session:
    shift = college.shift(s.shift_id)
    return s.model_copy(update={
        "day": day, "start_period": p, "venue_id": venue_id,
        "start": shift.periods[p].start, "end": shift.periods[p + s.length - 1].end,
    })


def occurrences(college: College, tt: Timetable, d: str) -> list[Occurrence]:
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
                out.append(Occurrence(session=s, date=d, status="normal"))
            elif o.kind == "cancel":
                out.append(Occurrence(session=s, date=d, status="cancelled", override_id=o.id,
                                      note=o.reason or "Cancelled for this day"))
            else:
                target = college.shift(s.shift_id).periods[o.start_period].start
                out.append(Occurrence(session=s, date=d, status="moved_out", override_id=o.id,
                                      note=f"Moved to {label(o.to_date)} {target}"))
    for o in tt.overrides:
        if o.kind == "move" and o.to_date == d and o.session_id in by_id:
            twd = weekday(college, d)
            if twd is None:
                continue
            s = _placed(college, by_id[o.session_id], twd, o.start_period, o.venue_id)
            out.append(Occurrence(session=s, date=d, status="moved_in", override_id=o.id,
                                  note=f"Moved from {label(o.date)} {by_id[o.session_id].start}"
                                  + (f" · {o.reason}" if o.reason else "")))
    return out


def active(college: College, tt: Timetable, d: str) -> list[Session]:
    return [o.session for o in occurrences(college, tt, d) if o.status in ("normal", "moved_in")]


def day_options(college: College, tt: Timetable, session_id: str, from_date: str, to_date: str) -> list[MoveOption]:
    """Free slots on ``to_date`` for moving one occurrence. Anything that would disturb others is blocked."""
    s = next(x for x in tt.sessions if x.id == session_id)
    wd = weekday(college, to_date)
    if wd is None:
        return []
    others = [x for x in active(college, tt, to_date) if x.id != s.id]
    out = []
    for p in range(len(college.shift(s.shift_id).periods)):
        if to_date == from_date and p == s.start_period:
            continue
        opt = check_slot(college, s, wd, p, others, tt.lunches, same_day_ok=(to_date == from_date))
        if opt is None:
            continue
        if opt.status == "repair":  # one-day changes never reshuffle other classes
            opt.status = "blocked"
            opt.reason = opt.reason.replace("; those would be rearranged.", ".") or "Not free that day."
        out.append(opt)
    return out


def add_override(
    college: College, tt: Timetable, session_id: str, d: str, kind: str, to_date: str | None,
    start_period: int | None, reason: str, actor: str,
) -> tuple[Timetable | None, str, str]:
    """Returns (new timetable, message for the user, audit sentence) or (None, error, "")."""
    s = next((x for x in tt.sessions if x.id == session_id), None)
    if s is None:
        return None, "Class not found.", ""
    if weekday(college, d) != s.day:
        return None, f"{college.subject(s.subject_id).name} doesn't happen on {label(d)}.", ""
    if any(o.session_id == session_id and o.date == d for o in tt.overrides):
        return None, "This class already has a change for that day. Restore it first.", ""

    subj = college.subject(s.subject_id).name
    secs = " + ".join(college.section(i).name for i in s.section_ids)
    if kind == "cancel":
        ov = Override(id=uuid.uuid4().hex[:10], session_id=s.id, date=d, kind="cancel", reason=reason,
                      created_by=actor)
        new = tt.model_copy(update={"overrides": [*tt.overrides, ov]})
        return (new, f"{subj} is cancelled on {label(d)} only. The weekly plan is unchanged.",
                f"Cancelled {subj} ({secs}) on {label(d)}")

    if kind != "move" or to_date is None or start_period is None:
        return None, "Choose a day and time to move the class to.", ""
    opt = next((o for o in day_options(college, tt, session_id, d, to_date) if o.start_period == start_period), None)
    if opt is None or opt.status != "free":
        return None, (opt.reason if opt else "That time isn't available."), ""
    ov = Override(id=uuid.uuid4().hex[:10], session_id=s.id, date=d, kind="move", to_date=to_date,
                  start_period=start_period, venue_id=opt.venue_id, reason=reason, created_by=actor)
    new = tt.model_copy(update={"overrides": [*tt.overrides, ov]})
    # Golden rule #1 on the real day: nothing on that date may clash.
    if validate(college, active(college, new, to_date), new.lunches, check_counts=False):
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
    if validate(college, active(college, new, ov.date), new.lunches, check_counts=False):
        return None, "Restoring would clash with another change made that day."
    subj = college.subject(s.subject_id).name
    return new, f"Restored {subj} on {label(ov.date)} to its usual time"
