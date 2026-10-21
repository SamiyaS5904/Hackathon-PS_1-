"""Editing a timetable safely: where can a class go, and repair when it clashes.

Flow (root CLAUDE.md §6): request -> repair (everything else frozen) -> validator
-> preview diff -> apply. Nothing here mutates the stored timetable.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from app.models.domain import College, Kind, Session, Timetable, VenueType
from app.solver.feasibility import group_ids
from app.solver.generate import Pin, generate
from app.validator.check import validate


def _m(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


class MoveOption(BaseModel):
    day: str
    start_period: int
    start: str
    end: str
    status: str  # "free" (direct move) | "repair" (others must shift) | "blocked"
    reason: str = ""
    venue_id: str | None = None  # room for a direct move
    conflicts: list[str] = []  # session ids that would have to move


class Change(BaseModel):
    session_id: str
    subject: str
    sections: str
    before: str  # "Mon 10:10-11:00 · LH-101"
    after: str


def _groups(college: College, s: Session) -> set[str]:
    if s.batch_id:
        return {s.batch_id}
    return {g for sid in s.section_ids for g in group_ids(college.section(sid))}


def _fits(college: College, s: Session, venue_id: str) -> bool:
    v = college.venue(venue_id)
    subj = college.subject(s.subject_id)
    if s.batch_id:
        sec = college.section(s.section_ids[0])
        strength = next(b.strength for b in sec.batches if b.id == s.batch_id)
    else:
        strength = sum(college.section(i).strength for i in s.section_ids)
    if v.capacity < strength:
        return False
    if s.kind == Kind.lab:
        return v.type == VenueType.lab and (subj.lab_tag is None or subj.lab_tag in v.tags)
    return v.type in (VenueType.lecture, VenueType.seminar)


def check_slot(
    college: College, s: Session, day: str, p: int, others: list[Session], lunches: list, same_day_ok: bool = False,
) -> MoveOption | None:
    """Can session ``s`` start at period ``p`` on ``day`` given the ``others``? None if p is out of range.

    ``same_day_ok``: the class is moving within its own day, so another lecture of the
    same subject that day doesn't count as a repeat.
    """
    shift = college.shift(s.shift_id)
    if p + s.length > len(shift.periods):
        return None
    teacher = college.teacher(s.teacher_id)
    groups = _groups(college, s)
    years = {college.section(i).year for i in s.section_ids}
    lunch = {ln.period for ln in lunches if ln.shift_id == s.shift_id and ln.year in years}
    idx = range(p, p + s.length)
    begin, end = shift.periods[p].start_min, shift.periods[p + s.length - 1].end_min
    opt = MoveOption(day=day, start_period=p, start=shift.periods[p].start, end=shift.periods[p + s.length - 1].end,
                     status="blocked")
    if any(shift.periods[i].end != shift.periods[i + 1].start for i in range(p, p + s.length - 1)):
        opt.reason = "A lab can't run across a break."
    elif lunch & set(idx):
        opt.reason = "That's the lunch period for these students."
    elif any(b.day == day and begin < _m(b.end) and _m(b.start) < end for b in teacher.blocked):
        opt.reason = f"{teacher.name} has blocked this time."
    elif any(br for br in shift.year_breaks if set(br.years) & years and begin < _m(br.end) and _m(br.start) < end):
        opt.reason = "Overlaps a fixed break."
    else:
        clash = [
            o for o in others
            if o.day == day and _m(o.start) < end and begin < _m(o.end)
            and (o.teacher_id == s.teacher_id or _groups(college, o) & groups)
        ]
        same_subject = [
            o for o in others
            if o.day == day and o.allotment_id == s.allotment_id and s.kind == Kind.lecture and not same_day_ok
        ]
        load = sum(o.length for o in others if o.teacher_id == s.teacher_id and o.day == day) + s.length
        busy_rooms = {o.venue_id for o in others if o.day == day and _m(o.start) < end and begin < _m(o.end)}
        if not clash and not same_subject and load <= teacher.max_per_day:
            rooms = [s.venue_id] + [v.id for v in college.venues if v.id != s.venue_id]
            room = next((r for r in rooms if r not in busy_rooms and _fits(college, s, r)), None)
            if room:
                opt.status, opt.venue_id = "free", room
                if room != s.venue_id:
                    opt.reason = f"Moves to {college.venue(room).name} (current room is busy)."
            else:
                opt.status, opt.reason = "repair", "No suitable room is free; other classes would shift."
        else:
            opt.status = "repair"
            opt.conflicts = [o.id for o in clash + same_subject]
            parts = []
            names = sorted({college.subject(o.subject_id).code for o in clash})
            if names:
                parts.append(f"Clashes with {', '.join(names)}")
            if same_subject:
                parts.append(f"{college.subject(s.subject_id).code} already has a lecture on {day} (max one a day)")
            opt.reason = (
                f"{'; '.join(parts)}; those would be rearranged." if parts
                else f"{teacher.name} would exceed {teacher.max_per_day} periods that day."
            )
    return opt


def move_options(college: College, tt: Timetable, session_id: str) -> list[MoveOption]:
    """Every slot in the weekly template the class could move to, and what that would take."""
    s = next(x for x in tt.sessions if x.id == session_id)
    shift = college.shift(s.shift_id)
    others = [x for x in tt.sessions if x.id != s.id]
    out: list[MoveOption] = []
    for day in college.days:
        for p in range(len(shift.periods)):
            if day == s.day and p == s.start_period:
                continue
            opt = check_slot(college, s, day, p, others, tt.lunches, same_day_ok=(day == s.day))
            if opt:
                out.append(opt)
    return out


def _describe(college: College, s: Session) -> str:
    return f"{s.day} {s.start}-{s.end} · {college.venue(s.venue_id).name}"


def diff(college: College, before: list[Session], after: list[Session]) -> list[Change]:
    """Classes whose placement changed, matched by session id (ids are kept stable through repairs)."""
    old = {s.id: s for s in before}
    changes = []
    for n in after:
        o = old.get(n.id)
        if o is None or (o.day, o.start_period, o.venue_id) == (n.day, n.start_period, n.venue_id):
            continue
        batch = ""
        if o.batch_id:
            batch = f" ({next(bt.name for bt in college.section(o.section_ids[0]).batches if bt.id == o.batch_id)})"
        changes.append(Change(
            session_id=o.id,
            subject=college.subject(o.subject_id).name,
            sections=" + ".join(college.section(i).name for i in o.section_ids) + batch,
            before=_describe(college, o),
            after=_describe(college, n),
        ))
    return changes


def _with_ids(old: list[Session], new: list[Session], forced: tuple[str, str, int] | None = None) -> list[Session]:
    """Give the repaired sessions the old ids so each class keeps its identity.

    ``forced`` = (session id, day, start): the class the user moved keeps its id at its new slot.
    Then unchanged placements keep their ids, and the remaining ones are paired by allotment.
    """
    by_old = defaultdict(list)
    for s in old:
        by_old[s.allotment_id].append(s)
    old_by_id = {s.id: s for s in old}
    out, used, pending = [], set(), list(new)

    if forced:
        sid, day, start = forced
        allot = old_by_id[sid].allotment_id
        n = next(x for x in pending if x.allotment_id == allot and (x.day, x.start_period) == (day, start))
        pending.remove(n)
        used.add(sid)
        out.append(n.model_copy(update={"id": sid}))

    rest = []
    for n in pending:
        match = next((o for o in by_old[n.allotment_id]
                      if o.id not in used and (o.day, o.start_period) == (n.day, n.start_period)), None)
        if match:
            used.add(match.id)
            out.append(n.model_copy(update={"id": match.id}))
        else:
            rest.append(n)
    for n in rest:
        match = next(o for o in by_old[n.allotment_id] if o.id not in used)
        used.add(match.id)
        out.append(n.model_copy(update={"id": match.id}))
    return out


def repair_move(
    college: College, tt: Timetable, session_id: str, day: str, start_period: int,
    venue_id: str | None = None, time_limit: float = 15.0,
) -> tuple[Timetable | None, str]:
    """Place one session at a new slot; let only clashing classes move, keep everything else frozen.

    Tries a small neighbourhood first, then a wider one (same teacher / students that day).
    Returns (new timetable, message). The result has always passed the validator.
    """
    moved = next(x for x in tt.sessions if x.id == session_id)
    options = {(o.day, o.start_period): o for o in move_options(college, tt, session_id)}
    opt = options.get((day, start_period))
    if opt is None or opt.status == "blocked":
        return None, (opt.reason if opt else "That slot isn't available.")

    shift = college.shift(moved.shift_id)
    begin, end = shift.periods[start_period].start_min, shift.periods[start_period + moved.length - 1].end_min
    groups = _groups(college, moved)
    lunch_pins = {(ln.shift_id, ln.year): ln.period for ln in tt.lunches}

    def attempt(free_ids: set[str]) -> Timetable | None:
        pins: dict[str, list[Pin]] = defaultdict(list)
        for s in tt.sessions:
            if s.id == session_id:
                pins[s.allotment_id].append(Pin(day=day, start=start_period, venue_id=venue_id or opt.venue_id))
            elif s.id not in free_ids:
                pins[s.allotment_id].append(Pin(day=s.day, start=s.start_period, venue_id=s.venue_id))
        result = generate(college, time_limit=time_limit, pins=dict(pins), lunch_pins=lunch_pins)
        if result.status in ("optimal", "feasible") and not validate(college, result.sessions, result.lunches):
            return result
        return None

    # 1) Direct move (only valid if nothing else needs to move).
    if opt.status == "free":
        new = [s if s.id != session_id else s.model_copy(update={
            "day": day, "start_period": start_period, "venue_id": opt.venue_id,
            "start": shift.periods[start_period].start, "end": shift.periods[start_period + moved.length - 1].end,
        }) for s in tt.sessions]
        if venue_id and venue_id != opt.venue_id:
            new = [s if s.id != session_id else s.model_copy(update={"venue_id": venue_id}) for s in new]
        candidate = tt.model_copy(update={"sessions": new})
        if not validate(college, candidate.sessions, candidate.lunches):
            return candidate, "Moved. Nothing else had to change."

    # 2) Free the clashing classes. 3) Widen to everything those teachers/students have on both days.
    small = set(opt.conflicts)
    target_room_users = {
        s.id for s in tt.sessions
        if s.day == day and _m(s.start) < end and begin < _m(s.end) and s.id != session_id
        and (venue_id and s.venue_id == venue_id)
    }
    involved_teachers = {moved.teacher_id} | {s.teacher_id for s in tt.sessions if s.id in small}
    involved_groups = set(groups) | {g for s in tt.sessions if s.id in small for g in _groups(college, s)}
    wide = small | target_room_users | {
        s.id for s in tt.sessions
        if s.id != session_id and s.day in (day, moved.day)
        and (s.teacher_id in involved_teachers or _groups(college, s) & involved_groups)
    }
    for free in (small | target_room_users, wide):
        result = attempt(free)
        if result:
            sessions = _with_ids(tt.sessions, result.sessions, forced=(session_id, day, start_period))
            new_tt = tt.model_copy(update={"sessions": sessions})
            n = len(diff(college, tt.sessions, sessions)) - 1
            return new_tt, (f"Moved. {n} other class{'es' if n != 1 else ''} rearranged to avoid clashes."
                            if n > 0 else "Moved. Nothing else had to change.")
    return None, "No clash-free way to make this move without changing more of the timetable."
