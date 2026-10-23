"""Flexible lunch: every section gets a free period inside its shift's mess window, every day.

The solver chooses the period per section and per day (CSE-2A may eat at 11:30 on Monday
and 13:30 on Tuesday) so the timetable stays compact. After an edit the lunches are
re-picked from what is still free, keeping each section's existing lunch when possible.
A change is only allowed if every section involved still has a free lunch period that day.

The validator checks the same rule with its own code (it must stay independent).
"""

from __future__ import annotations

from app.models.domain import College, Lunch, Section, Session, Timetable
from app.solver.feasibility import available_periods, group_ids
from app.solver.generate import session_groups


def _m(hhmm: str) -> int:
    h, mm = hhmm.split(":")
    return int(h) * 60 + int(mm)


def candidates(college: College, section: Section) -> list[int]:
    """Period indices that can be this section's lunch: fully inside the mess window, not a fixed break."""
    shift = college.shift(section.shift_id)
    allowed = set(available_periods(college, section.shift_id, section.year))
    return [p for p in shift.lunch_candidates() if p in allowed]


def free_periods(college: College, sessions: list[Session], section: Section, day: str,
                 extra: tuple[int, int] | None = None) -> list[int]:
    """Lunch candidates on ``day`` with no class for any of the section's groups (``extra``: a class
    about to be placed there, as minutes)."""
    shift = college.shift(section.shift_id)
    groups = set(group_ids(section))
    busy = [(_m(s.start), _m(s.end)) for s in sessions
            if s.day == day and groups & set(session_groups(college, s))]
    if extra:
        busy.append(extra)
    return [p for p in candidates(college, section)
            if not any(a < shift.periods[p].end_min and shift.periods[p].start_min < b for a, b in busy)]


def keeps_lunch(college: College, sessions: list[Session], section: Section, day: str,
                extra: tuple[int, int] | None = None) -> bool:
    if college.shift(section.shift_id).lunch is None:
        return True
    return bool(free_periods(college, sessions, section, day, extra))


def assign(college: College, sessions: list[Session], previous: list[Lunch] | None = None) -> list[Lunch]:
    """Pick each section's lunch for each working day from its free mess-window periods.

    A section keeps its previous lunch for that day when it is still free; otherwise the free
    period nearest the middle of the window. Sections with no free period get no entry (the
    validator then reports it)."""
    prev = {(ln.section_id, ln.day): ln.period for ln in previous or [] if ln.section_id}
    out: list[Lunch] = []
    for sec in college.sections:
        shift = college.shift(sec.shift_id)
        if shift.lunch is None:
            continue
        cands = candidates(college, sec)
        middle = cands[len(cands) // 2] if cands else 0
        for day in college.days:
            free = free_periods(college, sessions, sec, day)
            if not free:
                continue
            p = prev.get((sec.id, day))
            if p not in free:
                p = min(free, key=lambda q: (abs(q - middle), q))
            per = shift.periods[p]
            out.append(Lunch(shift_id=sec.shift_id, section_id=sec.id, day=day, period=p, start=per.start, end=per.end))
    return out


def for_day(college: College, sessions: list[Session], day: str, previous: list[Lunch] | None = None) -> list[Lunch]:
    """Lunches on one real date (``sessions`` = what actually happens that date, weekday ``day``)."""
    return [ln for ln in assign(college, [s for s in sessions if s.day == day], previous) if ln.day == day]


def upgrade(college: College, tt: Timetable) -> Timetable:
    """Older timetables stored one lunch per year for every day; turn them into per-section, per-day entries."""
    if not tt.lunches or all(ln.section_id for ln in tt.lunches):
        return tt
    legacy = {(ln.shift_id, ln.year): ln.period for ln in tt.lunches if ln.section_id is None}
    previous = [ln for ln in tt.lunches if ln.section_id]
    for sec in college.sections:
        p = legacy.get((sec.shift_id, sec.year))
        if p is None:
            continue
        per = college.shift(sec.shift_id).periods[p]
        previous += [Lunch(shift_id=sec.shift_id, section_id=sec.id, day=d, period=p, start=per.start, end=per.end)
                     for d in college.days]
    return tt.model_copy(update={"lunches": assign(college, tt.sessions, previous)})
