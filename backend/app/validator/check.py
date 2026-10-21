"""Independent timetable validator.

Golden rule #1: no clash ever reaches a user. This module re-checks every hard
rule from scratch using only the domain models -- it must NOT import anything
from ``app.solver`` (so a solver bug can't hide itself) or OR-Tools.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from pydantic import BaseModel

from app.models.domain import College, Kind, Lunch, Session, VenueType


class Violation(BaseModel):
    type: str
    message: str
    session_ids: list[str] = []


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _groups(section) -> list[str]:
    return [b.id for b in section.batches] if section.batches else [f"{section.id}:all"]


def validate(college: College, sessions: list[Session], lunches: list[Lunch] | None = None) -> list[Violation]:
    out: list[Violation] = []
    lunches = lunches or []
    sections = {s.id: s for s in college.sections}
    teachers = {t.id: t for t in college.teachers}
    venues = {v.id: v for v in college.venues}
    subjects = {s.id: s for s in college.subjects}
    shifts = {s.id: s for s in college.shifts}
    allotments = {a.id: a for a in college.allotments}

    def bad(kind: str, msg: str, *ss: Session) -> None:
        out.append(Violation(type=kind, message=msg, session_ids=[s.id for s in ss]))

    # Time interval of each session, computed from the shift's periods (not trusted from the session).
    interval: dict[str, tuple[int, int]] = {}
    groups_of: dict[str, list[str]] = {}

    for s in sessions:
        a = allotments.get(s.allotment_id)
        if a is None or s.teacher_id not in teachers or s.venue_id not in venues or s.shift_id not in shifts:
            bad("unknown_reference", f"Session {s.id} refers to something that doesn't exist.", s)
            continue
        if s.day not in college.days:
            bad("bad_day", f"Session {s.id} is on {s.day}, which is not a working day.", s)
            continue
        if (a.teacher_id, a.subject_id, sorted(a.section_ids), a.batch_id, a.kind) != (
            s.teacher_id, s.subject_id, sorted(s.section_ids), s.batch_id, s.kind,
        ):
            bad("allotment_mismatch", f"Session {s.id} doesn't match its allotment {a.id}.", s)

        shift = shifts[s.shift_id]
        subj = subjects[s.subject_id]
        teacher = teachers[s.teacher_id]
        venue = venues[s.venue_id]
        secs = [sections[i] for i in s.section_ids]
        name = f"{subj.name} ({', '.join(x.name for x in secs)})"

        # Periods exist and are back-to-back.
        expected_len = college.lab_periods if s.kind == Kind.lab else 1
        if s.length != expected_len:
            bad("wrong_length", f"{name} on {s.day} is {s.length} period(s); expected {expected_len}.", s)
        last = s.start_period + s.length - 1
        if s.start_period < 0 or last >= len(shift.periods):
            bad("bad_period", f"{name} on {s.day} runs outside the {shift.name} shift.", s)
            continue
        for i in range(s.start_period, last):
            if shift.periods[i].end != shift.periods[i + 1].start:
                bad("split_block", f"{name} on {s.day} is split by a break.", s)
        begin, end = _m(shift.periods[s.start_period].start), _m(shift.periods[last].end)
        interval[s.id] = (begin, end)
        if (s.start, s.end) != (shift.periods[s.start_period].start, shift.periods[last].end):
            bad("time_mismatch", f"{name} on {s.day} shows the wrong clock time.", s)

        # Shift rules (strict).
        for sec in secs:
            if sec.shift_id != s.shift_id:
                bad("wrong_shift", f"{name}: {sec.name} belongs to another shift.", s)
            for br in shift.year_breaks:
                if sec.year in br.years and begin < _m(br.end) and _m(br.start) < end:
                    bad("during_break", f"{name} on {s.day} overlaps {br.label} for year {sec.year}.", s)
        if s.shift_id not in teacher.shift_ids:
            bad("teacher_shift", f"{teacher.name} doesn't teach in the {shift.name} shift.", s)
        for blk in teacher.blocked:
            if blk.day == s.day and begin < _m(blk.end) and _m(blk.start) < end:
                bad("teacher_blocked", f"{teacher.name} is blocked on {s.day} {blk.start}-{blk.end}.", s)

        # Venue fit.
        if s.batch_id:
            batch = next((b for b in secs[0].batches if b.id == s.batch_id), None)
            if batch is None:
                bad("unknown_reference", f"{name}: unknown batch {s.batch_id}.", s)
                continue
            strength, groups = batch.strength, [batch.id]
        else:
            strength = sum(x.strength for x in secs)
            groups = [g for x in secs for g in _groups(x)]
        groups_of[s.id] = groups
        if venue.capacity < strength:
            bad("venue_too_small", f"{name}: {venue.name} holds {venue.capacity}, needs {strength}.", s)
        if s.kind == Kind.lab:
            if venue.type != VenueType.lab:
                bad("venue_type", f"{name}: lab placed in {venue.name}, which is not a lab.", s)
            elif subj.lab_tag and subj.lab_tag not in venue.tags:
                bad("venue_type", f"{name}: {venue.name} lacks '{subj.lab_tag}'.", s)
        elif venue.type == VenueType.lab:
            bad("venue_type", f"{name}: lecture placed in lab {venue.name}.", s)

    # Weekly counts per allotment.
    count: dict[str, int] = defaultdict(int)
    for s in sessions:
        count[s.allotment_id] += 1
    for a in college.allotments:
        subj = subjects.get(a.subject_id)
        if subj is None:
            continue
        need = subj.lectures_per_week if a.kind == Kind.lecture else subj.labs_per_week
        if count[a.id] != need:
            sec_names = ", ".join(sections[i].name for i in a.section_ids if i in sections)
            out.append(
                Violation(
                    type="wrong_count",
                    message=f"{subj.name} ({sec_names}) has {count[a.id]} {a.kind.value}(s) a week; needs {need}.",
                )
            )

    # Clashes: same day, overlapping time, shared teacher / venue / student group.
    by_day: dict[str, list[Session]] = defaultdict(list)
    for s in sessions:
        if s.id in interval:
            by_day[s.day].append(s)
    for day, items in by_day.items():
        for a, b in combinations(items, 2):
            (a0, a1), (b0, b1) = interval[a.id], interval[b.id]
            if not (a0 < b1 and b0 < a1):
                continue
            when = f"{day} {max(a.start, b.start)}"
            if a.teacher_id == b.teacher_id:
                bad("teacher_clash", f"{teachers[a.teacher_id].name} is double-booked on {when}.", a, b)
            if a.venue_id == b.venue_id:
                bad("venue_clash", f"{venues[a.venue_id].name} is double-booked on {when}.", a, b)
            shared = set(groups_of.get(a.id, [])) & set(groups_of.get(b.id, []))
            if shared:
                bad("student_clash", f"Students of {_group_label(college, shared)} have two classes on {when}.", a, b)

    # Flexible lunch: each year in a shift with a mess window gets exactly one
    # lunch period inside the window, and none of its students have class then.
    for sh in college.shifts:
        if sh.lunch is None:
            continue
        lo, hi = _m(sh.lunch.window_start), _m(sh.lunch.window_end)
        for year in sorted({x.year for x in college.sections if x.shift_id == sh.id}):
            mine = [ln for ln in lunches if ln.shift_id == sh.id and ln.year == year]
            if len(mine) != 1:
                out.append(Violation(type="lunch_missing",
                                     message=f"Year {year} ({sh.name}) needs exactly one lunch period; found {len(mine)}."))
                continue
            ln = mine[0]
            if not 0 <= ln.period < len(sh.periods):
                out.append(Violation(type="lunch_outside_window", message=f"Year {year} lunch period doesn't exist."))
                continue
            p = sh.periods[ln.period]
            if not (lo <= _m(p.start) and _m(p.end) <= hi):
                out.append(Violation(type="lunch_outside_window",
                                     message=f"Year {year} lunch {p.start}-{p.end} is outside the mess window."))
            year_groups = {g for x in college.sections if x.shift_id == sh.id and x.year == year for g in _groups(x)}
            for s in sessions:
                if s.id not in interval or not set(groups_of.get(s.id, [])) & year_groups:
                    continue
                b0, b1 = interval[s.id]
                if b0 < _m(p.end) and _m(p.start) < b1:
                    bad("class_during_lunch", f"{subjects[s.subject_id].name} on {s.day} is during year {year} lunch.", s)

    # Teacher daily limit.
    load: dict[tuple[str, str], int] = defaultdict(int)
    for s in sessions:
        load[(s.teacher_id, s.day)] += s.length
    for (tid, day), n in load.items():
        t = teachers.get(tid)
        if t and n > t.max_per_day:
            out.append(
                Violation(type="teacher_overload", message=f"{t.name} has {n} periods on {day}; limit is {t.max_per_day}.")
            )

    return out


def _group_label(college: College, groups: set[str]) -> str:
    names = []
    for sec in college.sections:
        for g in groups:
            if g == f"{sec.id}:all":
                names.append(sec.name)
            for b in sec.batches:
                if b.id == g:
                    names.append(f"{sec.name} {b.name}")
    return ", ".join(sorted(set(names)))
