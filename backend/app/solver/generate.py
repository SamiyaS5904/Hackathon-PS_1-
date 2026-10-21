"""College-wide timetable generation with Google OR-Tools CP-SAT.

Model
-----
Each allotment becomes one *unit* that needs ``count`` placements a week
(lectures: 1 period each; labs: one block of the college lab length). For each
unit we create a boolean ``x[u, day, start, venue]`` only for placements that are
already legal on their own (right shift, no fixed break, teacher not blocked,
venue of the right type and size, lab block contiguous). Deciding per allotment
instead of per identical lecture removes symmetry and keeps the search fast.

Hard constraints
  * each allotment placed exactly ``count`` times a week, at most once a day
  * no overlap per teacher, per venue and per student group (batch) -- checked at
    every period start time of every shift, so overlapping shifts that share
    venues/teachers are handled correctly
  * teacher max periods per day
  * flexible lunch: one period per (shift, year) inside the mess window, students free

Soft objective (minimised)
  * gaps in a student group's day (counted as extra "starts" of a block)
  * teacher's heaviest day (spreads load across the week)
  * empty seats and borrowing another department's room
  * a section's lectures spread over many rooms (prefer a home room)

The result is always re-checked by ``app.validator`` (independent code).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.models.domain import (
    College,
    Kind,
    Lunch,
    Session,
    Timetable,
    VenueType,
    to_hhmm,
)
from app.solver import feasibility
from app.solver.feasibility import available_periods, group_ids, lab_starts

W_GAP = 3
W_TEACHER_PEAK = 2
W_FOREIGN_ROOM = 2
W_ROOM_SPREAD = 3


@dataclass
class Unit:
    """One allotment to be placed ``count`` times a week."""

    allotment_id: str
    subject_id: str
    teacher_id: str
    kind: Kind
    section_ids: list[str]
    batch_id: str | None
    shift_id: str
    count: int
    length: int
    strength: int
    groups: list[str]
    home_department: str
    lab_tag: str | None
    years: set[int]


def build_units(college: College) -> list[Unit]:
    units: list[Unit] = []
    for a in college.allotments:
        subj = college.subject(a.subject_id)
        sections = [college.section(sid) for sid in a.section_ids]
        if a.batch_id:
            batch = next(b for b in sections[0].batches if b.id == a.batch_id)
            strength, groups = batch.strength, [batch.id]
        else:
            strength = sum(s.strength for s in sections)
            groups = [g for s in sections for g in group_ids(s)]
        if a.kind == Kind.lecture:
            count, length = subj.lectures_per_week, 1
        else:
            count, length = subj.labs_per_week, college.lab_periods
        if count == 0:
            continue
        units.append(
            Unit(
                allotment_id=a.id,
                subject_id=subj.id,
                teacher_id=a.teacher_id,
                kind=a.kind,
                section_ids=list(a.section_ids),
                batch_id=a.batch_id,
                shift_id=sections[0].shift_id,
                count=count,
                length=length,
                strength=strength,
                groups=groups,
                home_department=sections[0].department_id,
                lab_tag=subj.lab_tag,
                years={s.year for s in sections},
            )
        )
    return units


def _candidate_starts(college: College, u: Unit, day: str) -> list[int]:
    shift = college.shift(u.shift_id)
    if u.kind == Kind.lab:
        starts = set.intersection(*(set(lab_starts(college, u.shift_id, y)) for y in u.years))
    else:
        starts = set.intersection(*(set(available_periods(college, u.shift_id, y)) for y in u.years))
    teacher = college.teacher(u.teacher_id)
    out = []
    for s in sorted(starts):
        begin = shift.periods[s].start_min
        end = shift.periods[s + u.length - 1].end_min
        if any(b.day == day and begin < _m(b.end) and _m(b.start) < end for b in teacher.blocked):
            continue
        out.append(s)
    return out


def _candidate_venues(college: College, u: Unit) -> list[tuple[str, int]]:
    """(venue_id, cost) pairs; cost = wasted seats (per 10) + borrowing penalty."""
    out = []
    for v in college.venues:
        if v.capacity < u.strength:
            continue
        if u.kind == Kind.lab:
            if v.type != VenueType.lab or (u.lab_tag and u.lab_tag not in v.tags):
                continue
        elif v.type not in (VenueType.lecture, VenueType.seminar):
            continue
        cost = (v.capacity - u.strength) // 10
        if v.department_id is not None and v.department_id != u.home_department:
            cost += W_FOREIGN_ROOM
        out.append((v.id, cost))
    return out


def _m(hhmm: str) -> int:
    h, mm = hhmm.split(":")
    return int(h) * 60 + int(mm)


def generate(college: College, time_limit: float = 30.0, workers: int = 8, log: bool = False) -> Timetable:
    t0 = time.perf_counter()
    problems = feasibility.check(college)
    if problems:
        return Timetable(college_id=college.id, status="invalid_input", messages=problems)

    units = build_units(college)
    model = cp_model.CpModel()
    days = college.days

    # All period start times (minutes) across every shift: overlap checkpoints.
    checkpoints = sorted({p.start_min for sh in college.shifts for p in sh.periods})

    x: dict[tuple[int, int, int, str], cp_model.IntVar] = {}
    unit_day: dict[tuple[int, int], list] = defaultdict(list)
    cover: dict[tuple[str, int, int], list] = defaultdict(list)  # (resource, day, minute)
    teacher_day: dict[tuple[str, int], list] = defaultdict(list)
    room_use: dict[tuple[str, str], list] = defaultdict(list)  # (section, venue) -> lecture vars
    cost_terms = []

    for ui, u in enumerate(units):
        shift = college.shift(u.shift_id)
        venues = _candidate_venues(college, u)
        for d, day in enumerate(days):
            for s in _candidate_starts(college, u, day):
                begin = shift.periods[s].start_min
                end = shift.periods[s + u.length - 1].end_min
                points = [c for c in checkpoints if begin <= c < end]
                for vid, cost in venues:
                    var = model.NewBoolVar(f"u{ui}_d{d}_s{s}_{vid}")
                    x[(ui, d, s, vid)] = var
                    unit_day[(ui, d)].append(var)
                    for c in points:
                        cover[(f"t:{u.teacher_id}", d, c)].append(var)
                        cover[(f"v:{vid}", d, c)].append(var)
                        for g in u.groups:
                            cover[(f"g:{g}", d, c)].append(var)
                    teacher_day[(u.teacher_id, d)].append((var, u.length))
                    if u.kind == Kind.lecture:
                        for sid in u.section_ids:
                            room_use[(sid, vid)].append(var)
                    if cost:
                        cost_terms.append(cost * var)

    # Each allotment: `count` times a week, at most once a day.
    for ui, u in enumerate(units):
        per_day = [unit_day.get((ui, d), []) for d in range(len(days))]
        if sum(1 for vs in per_day if vs) < u.count:
            subj = college.subject(u.subject_id)
            secs = ", ".join(college.section(i).name for i in u.section_ids)
            return Timetable(
                college_id=college.id,
                status="invalid_input",
                messages=[f"{subj.name} ({secs}) needs {u.count} days a week but has legal slots on fewer days "
                          "(check shift, breaks, teacher blocked times, rooms)."],
                solve_seconds=time.perf_counter() - t0,
            )
        for vs in per_day:
            if len(vs) > 1:
                model.AddAtMostOne(vs)
        model.Add(sum(v for vs in per_day for v in vs) == u.count)

    # No double booking of any teacher / venue / student group.
    for vars_ in cover.values():
        if len(vars_) > 1:
            model.AddAtMostOne(vars_)

    # Flexible lunch: pick one period per (shift, year) inside the mess window and
    # keep every student group of that year free then, on every day.
    lunch_vars: dict[tuple[str, int], dict[int, cp_model.IntVar]] = {}
    for sh in college.shifts:
        cands = sh.lunch_candidates()
        if not cands:
            continue
        for y in sorted({s.year for s in college.sections if s.shift_id == sh.id}):
            choice = {p: model.NewBoolVar(f"lunch_{sh.id}_{y}_{p}") for p in cands}
            model.AddExactlyOne(choice.values())
            lunch_vars[(sh.id, y)] = choice
            for sec in (s for s in college.sections if s.shift_id == sh.id and s.year == y):
                for g in group_ids(sec):
                    for d in range(len(days)):
                        for p, lv in choice.items():
                            busy = cover.get((f"g:{g}", d, sh.periods[p].start_min), [])
                            if busy:
                                model.Add(sum(busy) + lv <= 1)

    # Home room: each extra lecture room a section uses costs a little.
    for vars_ in room_use.values():
        used = model.NewBoolVar("")
        for v in vars_:
            model.AddImplication(v, used)
        cost_terms.append(W_ROOM_SPREAD * used)

    # Teacher daily limit + heaviest-day penalty.
    for t in college.teachers:
        peak = model.NewIntVar(0, t.max_per_day, f"peak_{t.id}")
        used = False
        for d in range(len(days)):
            items = teacher_day.get((t.id, d))
            if not items:
                continue
            load = sum(v * ln for v, ln in items)
            model.Add(load <= t.max_per_day)
            model.Add(peak >= load)
            used = True
        if used:
            cost_terms.append(W_TEACHER_PEAK * peak)

    # Compact days for every student group: penalise each extra block start.
    for s in college.sections:
        shift = college.shift(s.shift_id)
        chain = available_periods(college, s.shift_id, s.year)
        lunch = lunch_vars.get((s.shift_id, s.year), {})
        for g in group_ids(s):
            for d in range(len(days)):
                # Lunch counts as "occupied" so it never looks like a gap.
                occ = [
                    sum(cover.get((f"g:{g}", d, shift.periods[p].start_min), [])) + lunch.get(p, 0)
                    for p in chain
                ]
                prev = 0
                for o in occ:
                    st = model.NewBoolVar("")
                    model.Add(st >= o - prev)
                    cost_terms.append(W_GAP * st)
                    prev = o

    model.Minimize(sum(cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(time_limit - (time.perf_counter() - t0), 1.0)
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = log
    # Allotment-level variables already remove most symmetry, and heavy presolve
    # (symmetry, probing) costs more time than it saves here: spend it on search.
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.max_presolve_iterations = 1
    status = solver.Solve(model)
    elapsed = time.perf_counter() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        msg = (
            "No clash-free timetable exists with the current data and rules."
            if status == cp_model.INFEASIBLE
            else f"No timetable found within {time_limit:.0f}s. Try a longer time limit or fewer rules."
        )
        return Timetable(
            college_id=college.id,
            status="infeasible" if status == cp_model.INFEASIBLE else "timeout",
            messages=[msg],
            solve_seconds=round(elapsed, 2),
        )
    value = solver.Value
    objective = solver.ObjectiveValue()

    sessions: list[Session] = []
    for (ui, d, s, vid), var in x.items():
        if not value(var):
            continue
        u = units[ui]
        shift = college.shift(u.shift_id)
        sessions.append(
            Session(
                id=f"s{len(sessions) + 1}",
                allotment_id=u.allotment_id,
                subject_id=u.subject_id,
                teacher_id=u.teacher_id,
                venue_id=vid,
                kind=u.kind,
                section_ids=u.section_ids,
                batch_id=u.batch_id,
                day=days[d],
                shift_id=u.shift_id,
                start_period=s,
                length=u.length,
                start=to_hhmm(shift.periods[s].start_min),
                end=to_hhmm(shift.periods[s + u.length - 1].end_min),
            )
        )

    lunches = []
    for (sh_id, y), choice in lunch_vars.items():
        p = next(p for p, v in choice.items() if value(v))
        per = college.shift(sh_id).periods[p]
        lunches.append(Lunch(shift_id=sh_id, year=y, period=p, start=per.start, end=per.end))

    return Timetable(
        college_id=college.id,
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        sessions=sessions,
        lunches=lunches,
        solve_seconds=round(elapsed, 2),
        objective=objective,
    )
