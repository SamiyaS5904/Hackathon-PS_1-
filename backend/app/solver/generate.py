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
  * uneven student weeks: heavy days, and days with a single class

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
W_STUDENT_PEAK = 2
W_LIGHT_DAY = 6


@dataclass(frozen=True)
class Pin:
    """Force one placement of an allotment: on `day` at period `start`, in `venue_id` (or any fitting room)."""

    day: str
    start: int
    venue_id: str | None = None


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


def generate(
    college: College,
    time_limit: float = 30.0,
    workers: int = 8,
    log: bool = False,
    pins: dict[str, list[Pin]] | None = None,
    lunch_pins: dict[tuple[str, int], int] | None = None,
) -> Timetable:
    """Build a timetable.

    Full generation runs in two stages for speed and quality:
      A. times only (day + period for every class), with a room-count check so enough
         suitable rooms are always free;
      B. rooms for the fixed times (room fit, home room, own department first).
    If B can't place every class, the full model (times + rooms) is solved from A's times.

    ``pins`` fix placements per allotment (used by repair); then the full model is used directly,
    and an allotment pinned as many times as it meets a week is fully frozen.
    """
    t0 = time.perf_counter()
    problems = feasibility.check(college)
    if problems:
        return Timetable(college_id=college.id, status="invalid_input", messages=problems)
    notes = feasibility.warnings(college)
    units = build_units(college)

    def done(tt: Timetable) -> Timetable:
        tt.warnings = notes
        tt.solve_seconds = round(time.perf_counter() - t0, 2)
        return tt

    if pins:
        return done(_solve(college, units, time_limit, workers, log, pins, lunch_pins or {}, with_venues=True))

    stage_a = _solve(college, units, time_limit * 0.8, workers, log, {}, lunch_pins or {}, with_venues=False)
    if not stage_a.sessions:
        return done(stage_a)
    remaining = max(time_limit - (time.perf_counter() - t0), 5.0)
    roomed = assign_rooms(college, units, stage_a.sessions, remaining, workers)
    if roomed is not None:
        stage_a.sessions = roomed
        return done(stage_a)

    # Rare: rooms couldn't be matched to A's times; solve times + rooms together, starting from A.
    hints = {(s.allotment_id, s.day, s.start_period) for s in stage_a.sessions}
    lunch = {(ln.shift_id, ln.year): ln.period for ln in stage_a.lunches}
    return done(_solve(college, units, max(remaining, 20.0), workers, log, {}, lunch, with_venues=True, hints=hints))


def _solver(limit: float, workers: int, log: bool) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(limit, 1.0)
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = log
    # Allotment-level variables already remove most symmetry, and heavy presolve
    # (symmetry, probing) costs more time than it saves here: spend it on search.
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.max_presolve_iterations = 1
    return solver


def _solve(
    college: College,
    units: list[Unit],
    time_limit: float,
    workers: int,
    log: bool,
    pins: dict[str, list[Pin]],
    lunch_pins: dict[tuple[str, int], int],
    with_venues: bool,
    hints: set[tuple[str, str, int]] | None = None,
) -> Timetable:
    t0 = time.perf_counter()
    model = cp_model.CpModel()
    days = college.days

    def fail(status: str, msg: str) -> Timetable:
        return Timetable(college_id=college.id, status=status, messages=[msg])

    # All period start times (minutes) across every shift: overlap checkpoints.
    checkpoints = sorted({p.start_min for sh in college.shifts for p in sh.periods})

    # Room classes for the times-only stage: every distinct set of rooms a unit could use.
    venue_sets: list[frozenset[str]] = []
    unit_vset: dict[int, frozenset[str]] = {}
    for ui, u in enumerate(units):
        vs = frozenset(v for v, _ in _candidate_venues(college, u))
        unit_vset[ui] = vs
        if vs not in venue_sets:
            venue_sets.append(vs)
    subset_of = {ui: [k for k, S in enumerate(venue_sets) if vs <= S] for ui, vs in unit_vset.items()}

    x: dict[tuple[int, int, int, str | None], cp_model.IntVar] = {}
    unit_day: dict[tuple[int, int], list] = defaultdict(list)
    cover: dict[tuple[str, int, int], list] = defaultdict(list)  # (resource, day, minute)
    room_cover: dict[tuple[int, int, int], list] = defaultdict(list)  # (room class, day, minute)
    teacher_day: dict[tuple[str, int], list] = defaultdict(list)
    room_use: dict[tuple[str, str], list] = defaultdict(list)  # (section, venue) -> lecture vars
    group_day: dict[tuple[str, int], list] = defaultdict(list)  # (group, day) -> (var, periods)
    cost_terms = []

    for ui, u in enumerate(units):
        shift = college.shift(u.shift_id)
        venues = _candidate_venues(college, u) if with_venues else [(None, 0)]
        my_pins = pins.get(u.allotment_id, [])
        frozen = len(my_pins) >= u.count  # fully pinned: only create the pinned placements
        for d, day in enumerate(days):
            for s in _candidate_starts(college, u, day):
                if frozen and not any(p.day == day and p.start == s for p in my_pins):
                    continue
                begin = shift.periods[s].start_min
                end = shift.periods[s + u.length - 1].end_min
                points = [c for c in checkpoints if begin <= c < end]
                for vid, cost in venues:
                    if frozen and not any(
                        p.day == day and p.start == s and p.venue_id in (None, vid) for p in my_pins
                    ):
                        continue
                    var = model.NewBoolVar(f"u{ui}_d{d}_s{s}_{vid}")
                    x[(ui, d, s, vid)] = var
                    if hints is not None:
                        model.AddHint(var, (u.allotment_id, day, s) in hints)
                    unit_day[(ui, d)].append(var)
                    for c in points:
                        cover[(f"t:{u.teacher_id}", d, c)].append(var)
                        for g in u.groups:
                            cover[(f"g:{g}", d, c)].append(var)
                        if vid is not None:
                            cover[(f"v:{vid}", d, c)].append(var)
                        else:
                            for k in subset_of[ui]:
                                room_cover[(k, d, c)].append(var)
                    teacher_day[(u.teacher_id, d)].append((var, u.length))
                    for g in u.groups:
                        group_day[(g, d)].append((var, u.length))
                    if vid is not None and u.kind == Kind.lecture:
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
            return fail("invalid_input", f"{subj.name} ({secs}) needs {u.count} days a week but has legal slots on "
                        "fewer days (check shift, breaks, teacher blocked times, rooms).")
        for vs in per_day:
            if len(vs) > 1:
                model.AddAtMostOne(vs)
        model.Add(sum(v for vs in per_day for v in vs) == u.count)

    # Pinned placements (repair keeps everything else exactly where it is).
    for ui, u in enumerate(units):
        for p in pins.get(u.allotment_id, []):
            d = days.index(p.day) if p.day in days else -1
            options = [
                var for (vi, vd, vs, vid), var in x.items()
                if vi == ui and vd == d and vs == p.start and p.venue_id in (None, vid)
            ] if d >= 0 else []
            if not options:
                subj = college.subject(u.subject_id)
                return fail("infeasible", f"{subj.name} can't be placed on {p.day} at that time (break, shift, "
                            "teacher blocked, or no suitable room).")
            model.Add(sum(options) == 1)

    # No double booking of any teacher / venue / student group.
    for vars_ in cover.values():
        if len(vars_) > 1:
            model.AddAtMostOne(vars_)

    # Times-only stage: at every moment, classes that need rooms from a set never outnumber that set.
    for (k, _, _), vars_ in room_cover.items():
        if len(vars_) > len(venue_sets[k]):
            model.Add(sum(vars_) <= len(venue_sets[k]))

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
            if (sh.id, y) in lunch_pins and lunch_pins[(sh.id, y)] in choice:
                model.Add(choice[lunch_pins[(sh.id, y)]] == 1)
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

    # Even student weeks: lighten the heaviest day and avoid single-class days.
    for sec in college.sections:
        max_load = len(available_periods(college, sec.shift_id, sec.year))
        for g in group_ids(sec):
            peak = model.NewIntVar(0, max_load, "")
            for d in range(len(days)):
                items = group_day.get((g, d))
                if not items:
                    continue
                load = sum(v * ln for v, ln in items)
                model.Add(peak >= load)
                has = model.NewBoolVar("")
                model.Add(load >= has)
                model.Add(load <= max_load * has)
                light = model.NewBoolVar("")
                model.Add(light >= has - (load - 1))  # has classes and load == 1
                cost_terms.append(W_LIGHT_DAY * light)
            cost_terms.append(W_STUDENT_PEAK * peak)

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
    solver = _solver(time_limit - (time.perf_counter() - t0), workers, log)
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if status == cp_model.INFEASIBLE:
            return fail("infeasible", "No clash-free timetable exists with the current data and rules.")
        return fail("timeout", f"No timetable found within {time_limit:.0f}s. Try a longer time limit or fewer rules.")

    sessions: list[Session] = []
    for (ui, d, s, vid), var in x.items():
        if not solver.Value(var):
            continue
        u = units[ui]
        shift = college.shift(u.shift_id)
        sessions.append(
            Session(
                id=f"s{len(sessions) + 1}",
                allotment_id=u.allotment_id,
                subject_id=u.subject_id,
                teacher_id=u.teacher_id,
                venue_id=vid or "",
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
        p = next(p for p, v in choice.items() if solver.Value(v))
        per = college.shift(sh_id).periods[p]
        lunches.append(Lunch(shift_id=sh_id, year=y, period=p, start=per.start, end=per.end))

    return Timetable(
        college_id=college.id,
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        sessions=sessions,
        lunches=lunches,
        objective=solver.ObjectiveValue(),
    )


def assign_rooms(
    college: College, units: list[Unit], sessions: list[Session], time_limit: float, workers: int = 8,
) -> list[Session] | None:
    """Stage B: give every timed class a room. Returns None if some class can't get one."""
    model = cp_model.CpModel()
    by_allotment = {u.allotment_id: u for u in units}
    checkpoints = sorted({p.start_min for sh in college.shifts for p in sh.periods})
    y: dict[tuple[int, str], cp_model.IntVar] = {}
    cover: dict[tuple[str, str, int], list] = defaultdict(list)
    room_use: dict[tuple[str, str], list] = defaultdict(list)
    cost_terms = []
    for i, s in enumerate(sessions):
        u = by_allotment[s.allotment_id]
        begin, end = _m(s.start), _m(s.end)
        points = [c for c in checkpoints if begin <= c < end]
        options = _candidate_venues(college, u)
        if not options:
            return None
        for vid, cost in options:
            var = model.NewBoolVar(f"r{i}_{vid}")
            y[(i, vid)] = var
            for c in points:
                cover[(vid, s.day, c)].append(var)
            if s.kind == Kind.lecture:
                for sid in s.section_ids:
                    room_use[(sid, vid)].append(var)
            if cost:
                cost_terms.append(cost * var)
        model.AddExactlyOne(y[(i, vid)] for vid, _ in options)
    for vars_ in cover.values():
        if len(vars_) > 1:
            model.AddAtMostOne(vars_)
    for vars_ in room_use.values():
        used = model.NewBoolVar("")
        for v in vars_:
            model.AddImplication(v, used)
        cost_terms.append(W_ROOM_SPREAD * used)
    model.Minimize(sum(cost_terms))
    solver = _solver(time_limit, workers, False)
    if solver.Solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    out = []
    for i, s in enumerate(sessions):
        vid = next(v for (j, v), var in y.items() if j == i and solver.Value(var))
        out.append(s.model_copy(update={"venue_id": vid}))
    return out
