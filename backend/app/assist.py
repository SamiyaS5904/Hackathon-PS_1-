"""Read-only facts for the assistant (and the dashboard): free rooms, where a teacher is,
why a class sits where it does, and proactive insights after generation.

Everything here works on the *effective* timetable of a real date (weekly plan + one-day
changes + holidays) and returns only what any member of the college may know: room names,
teacher locations from the timetable, counts. Never student details.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from app.edits.moves import move_options
from app.edits.oneday import active, label, weekday
from app.models.domain import College, Kind, Timetable, VenueType
from app.solver.quality import score


def _m(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


class FreeRoom(BaseModel):
    venue_id: str
    name: str
    type: str
    capacity: int
    department: str | None
    free_until: str | None  # next booking that day, or None if free for the rest of the day


class TeacherNow(BaseModel):
    teacher: str
    date: str
    time: str
    status: str  # "teaching" | "free" | "not_working" | "holiday"
    subject: str | None = None
    room: str | None = None
    sections: str | None = None
    until: str | None = None
    next_class: str | None = None


class Explanation(BaseModel):
    session_id: str
    summary: str
    facts: list[str]


class Insight(BaseModel):
    kind: str  # "teacher_peak" | "idle_room" | "student_balance" | "borrowed_rooms" | "quality"
    severity: str  # "info" | "warn"
    title: str
    detail: str
    ask: str  # a question the user can send to the assistant to act on it


def free_rooms(college: College, tt: Timetable, d: str, time: str, min_seats: int = 0) -> list[FreeRoom]:
    if any(h.date == d for h in college.holidays) or weekday(college, d) is None:
        return [FreeRoom(venue_id=v.id, name=v.name, type=v.type.value, capacity=v.capacity, department=v.department_id,
                         free_until=None) for v in college.venues if v.capacity >= min_seats]
    t = _m(time)
    day = active(college, tt, d)
    out = []
    for v in sorted(college.venues, key=lambda v: (v.type != VenueType.lecture, v.capacity)):
        if v.capacity < min_seats:
            continue
        mine = sorted((s for s in day if s.venue_id == v.id), key=lambda s: s.start)
        if any(_m(s.start) <= t < _m(s.end) for s in mine):
            continue
        nxt = next((s.start for s in mine if _m(s.start) > t), None)
        out.append(FreeRoom(venue_id=v.id, name=v.name, type=v.type.value, capacity=v.capacity,
                            department=v.department_id, free_until=nxt))
    return out


def teacher_now(college: College, tt: Timetable, teacher_id: str, d: str, time: str) -> TeacherNow:
    t = college.teacher(teacher_id)
    base = TeacherNow(teacher=t.name, date=label(d), time=time, status="free")
    if any(h.date == d for h in college.holidays):
        return base.model_copy(update={"status": "holiday"})
    if weekday(college, d) is None:
        return base.model_copy(update={"status": "not_working"})
    now = _m(time)
    mine = sorted((s for s in active(college, tt, d) if s.teacher_id == teacher_id), key=lambda s: s.start)
    cur = next((s for s in mine if _m(s.start) <= now < _m(s.end)), None)
    nxt = next((s for s in mine if _m(s.start) > now), None)
    nxt_txt = (f"{college.subject(nxt.subject_id).name} at {nxt.start} in {college.venue(nxt.venue_id).name}"
               if nxt else None)
    if cur is None:
        return base.model_copy(update={"next_class": nxt_txt})
    return base.model_copy(update={
        "status": "teaching", "subject": college.subject(cur.subject_id).name, "room": college.venue(cur.venue_id).name,
        "sections": " + ".join(college.section(i).name for i in cur.section_ids), "until": cur.end,
        "next_class": nxt_txt,
    })


def explain(college: College, tt: Timetable, session_id: str) -> Explanation:
    """Plain facts about why a class is where it is: the rules that bind it and how many alternatives exist."""
    s = next(x for x in tt.sessions if x.id == session_id)
    subj = college.subject(s.subject_id)
    teacher = college.teacher(s.teacher_id)
    shift = college.shift(s.shift_id)
    venue = college.venue(s.venue_id)
    day = f"{shift.periods[0].start}-{shift.periods[-1].end}"
    secs = ", ".join(college.section(i).name for i in s.section_ids)
    facts = [f"It is in the {shift.name} shift ({day}), the shift of {secs}." if len(college.shifts) > 1
             else f"Classes run {day}; {secs} can only be placed inside those hours."]
    if s.kind == Kind.lab:
        facts.append(f"Labs are {college.lab_periods} back-to-back periods without a break, in a lab with "
                     f"{subj.lab_tag or 'the right equipment'}.")
    if s.elective_slot_id:
        slot = college.elective_slot(s.elective_slot_id)
        facts.append(f"It is part of {slot.name}: all {len(slot.groups)} groups meet at the same time, so every "
                     "participating section is free of other classes then.")
    same_day = [x for x in tt.sessions if x.teacher_id == s.teacher_id and x.day == s.day and x.id != s.id]
    facts.append(f"{teacher.name} teaches {len(same_day) + 1} class(es) that day (limit {teacher.max_per_day} periods).")
    if teacher.blocked:
        facts.append(f"{teacher.name} is unavailable at " +
                     ", ".join(f"{b.day} {b.start}-{b.end}" for b in teacher.blocked) + ".")
    years = {college.section(i).year for i in s.section_ids}
    for ln in tt.lunches:
        if ln.shift_id == s.shift_id and ln.year in years:
            facts.append(f"Year {ln.year} has lunch at {ln.start}-{ln.end} every day.")
    for r in college.rules:
        if r.enabled and any(r.applies_to(college.section(i)) for i in s.section_ids):
            facts.append(f"Rule '{r.name}' ({r.mode}) applies.")
    room_size = sum(college.section(i).strength for i in s.section_ids) if not s.elective_slot_id else len(
        college.elective_group(s.elective_slot_id, s.group_id).student_ids)
    facts.append(f"{venue.name} seats {venue.capacity} for {room_size} students"
                 + (" (a borrowed room)" if venue.department_id and venue.department_id !=
                    college.section(s.section_ids[0]).department_id else "") + ".")
    if not s.elective_slot_id:
        opts = move_options(college, tt, session_id)
        free = sum(1 for o in opts if o.status == "free")
        repair = sum(1 for o in opts if o.status == "repair")
        facts.append(f"Other possible times this week: {free} free right away, {repair} more if other classes move.")
    summary = (f"{subj.name} is on {s.day} {s.start}-{s.end} in {venue.name}. The timetable places every class where "
               "no teacher, room or student clashes, then keeps students' days compact and teachers' loads even.")
    return Explanation(session_id=s.id, summary=summary, facts=facts)


def insights(college: College, tt: Timetable) -> list[Insight]:
    """Deterministic, data-backed insights (no AI): what an Admin or Coordinator might want to fix next."""
    out: list[Insight] = []
    if not tt.sessions:
        return out
    q = score(college, tt.sessions, tt.lunches)
    names = {t.id: t.name for t in college.teachers}
    # Teachers with a heavy day well above their even share.
    peaks = []
    for tid, loads in q.teacher_load.items():
        total = sum(loads.values())
        if not total:
            continue
        day, peak = max(loads.items(), key=lambda kv: kv[1])
        low_day, low = min(loads.items(), key=lambda kv: kv[1])
        if peak - low >= 3:
            peaks.append((peak - low, tid, day, peak, low_day, low))
    for _, tid, day, peak, low_day, low in sorted(peaks, reverse=True)[:2]:
        lighter = f"none on {low_day}" if low == 0 else f"only {low} on {low_day}"
        out.append(Insight(kind="teacher_peak", severity="warn", title=f"{names[tid]} has {peak} periods on {day}",
                           detail=f"And {lighter}. Moving one class would even out the week.",
                           ask=f"Rebalance {names[tid]}'s week: suggest moving one class from {day} to {low_day}."))
    # Rooms that sit empty most of the week.
    idle = sorted(((u, v) for v, u in q.venue_utilisation.items() if u < 0.15), key=lambda x: x[0])
    if idle:
        rooms = ", ".join(college.venue(v).name for _, v in idle[:4])
        one = len(idle) == 1
        out.append(Insight(kind="idle_room", severity="info",
                           title="1 room is almost unused" if one else f"{len(idle)} rooms are almost unused",
                           detail=f"{rooms} {'is' if one else 'are'} booked less than 15% of the week, "
                                  "free for extra or makeup classes.",
                           ask="Which rooms are almost unused, and when are they free?"))
    item = next((i for i in q.items if i.key == "student_balance"), None)
    if item and item.penalty >= 4:
        out.append(Insight(kind="student_balance", severity="warn", title="Some student weeks are uneven",
                           detail=item.detail, ask="Which sections have uneven weeks, and how could we fix them?"))
    borrowed = defaultdict(int)
    for s in tt.sessions:
        v = college.venue(s.venue_id)
        if not s.elective_slot_id and v.department_id and v.department_id != college.section(s.section_ids[0]).department_id:
            borrowed[college.section(s.section_ids[0]).department_id] += s.length
    for dept, n in sorted(borrowed.items(), key=lambda kv: -kv[1])[:1]:
        short = next((d.short for d in college.departments if d.id == dept), dept)
        out.append(Insight(kind="borrowed_rooms", severity="info", title=f"{short} borrows {n} room-periods a week",
                           detail="Its own rooms are full at those times, so other departments' free rooms are used.",
                           ask=f"When does {short} use other departments' rooms?"))
    out.insert(0, Insight(kind="quality", severity="info", title=f"Quality score {q.score}/100",
                          detail="; ".join(f"{i.label}: {i.detail}" for i in q.items if i.penalty > 0)[:300],
                          ask="Explain the quality score and the biggest thing we could improve."))
    return out[:5]
