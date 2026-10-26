"""College-wide timetable generation with Google OR-Tools CP-SAT.

Model
-----
Each allotment becomes one *unit* that needs ``count`` placements a week
(lectures: 1 period each; labs: one block of the college lab length). For each
unit we create a boolean ``x[u, day, start, venue]`` only for placements that are
already legal on their own (right shift, no fixed break, teacher not blocked,
venue of the right type and size, lab block contiguous). Deciding per allotment
instead of per identical lecture removes symmetry and keeps the search fast.

Each *elective slot* is one more unit ``z[slot, day, start]``: when it meets, all its
groups meet (one teacher and room each, any department) and every participating
section is busy.

Hard constraints
  * each allotment placed exactly ``count`` times a week, at most once a day
  * each elective slot meets ``lectures_per_week`` times, at most once a day
  * no overlap per teacher, per venue and per student group (batch) -- checked at
    every period start time of every shift, so overlapping shifts that share
    venues/teachers are handled correctly
  * teacher max periods per day
  * flexible lunch: one free period per section and per day inside the mess window

Soft objective (minimised)
  * gaps in a student group's day (counted as extra "starts" of a block)
  * teacher's heaviest day (spreads load across the week)
  * empty seats and borrowing another department's room
  * a section's lectures spread over many rooms (prefer a home room)
  * uneven student weeks: heavy days, and days with a single class

Generation runs in two stages (times, then rooms); repairs use the full model with
everything except the affected classes pinned. The result is always re-checked by
``app.validator`` (independent code).
"""

from __future__ import annotations

import os

import time
from collections import defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from app.models.domain import College, ElectiveSlot, Kind, Lunch, Session, Timetable, VenueType, to_hhmm
from app.solver import feasibility
from app.solver.feasibility import available_periods, group_ids, lab_starts

W_GAP = 3
W_TEACHER_PEAK = 2
W_FOREIGN_ROOM = 2
W_ROOM_SPREAD = 3
W_STUDENT_PEAK = 2
W_LIGHT_DAY = 6
W_RULE = 2  # x rule weight (1-10) for "try" rules
# Minimal-change regenerate: moving a class away from its current day/time costs far more than any
# quality gain, so only classes that must move (or gain a lot) move. A new room at the same time costs a little.
W_MOVE = 40
W_ROOM_MOVE = 4

# (allotment id, day, start period) -> venue id of the current timetable. Elective slots are also keyed
# as ("e:<slot id>", day, start) for their common time.
Keep = dict[tuple[str, str, int], str | None]


def _window_rules(college: College, section_ids: list[str], day: str, begin: int, end: int) -> int | None:
    """None if a Must "no classes" rule forbids this time for these sections, else the Try-rule cost."""
    cost = 0
    secs = [college.section(i) for i in section_ids]
    for rule in college.rules:
        if not rule.enabled or rule.kind != "no_classes" or not rule.blocks(day, begin, end):
            continue
        if any(rule.applies_to(s) for s in secs):
            if rule.mode == "must":
                return None
            cost += W_RULE * rule.weight * 3
    return cost


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


@dataclass
class ElectiveUnit:
    """One elective slot: all groups meet together, all participating sections are busy."""

    slot: ElectiveSlot
    shift_id: str
    years: set[int]
    groups: list[str]  # student groups (batches) of every participating section
    teacher_ids: list[str]
    count: int
    # per elective group: (group id, candidate venues with cost)
    rooms: list[tuple[str, list[tuple[str, int]]]] = field(default_factory=list)


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


def build_elective_units(college: College) -> list[ElectiveUnit]:
    out = []
    for slot in college.elective_slots:
        if slot.lectures_per_week == 0 or not slot.groups:
            continue
        sections = [college.section(sid) for sid in slot.section_ids]
        eu = ElectiveUnit(
            slot=slot,
            shift_id=sections[0].shift_id,
            years={s.year for s in sections},
            groups=[g for s in sections for g in group_ids(s)],
            teacher_ids=[g.teacher_id for g in slot.groups],
            count=slot.lectures_per_week,
        )
        for g in slot.groups:
            home = college.teacher(g.teacher_id).department_id  # e.g. an ME teacher teaches in ME rooms
            eu.rooms.append((g.id, _venues_for(college, len(g.student_ids), Kind.lecture, None, home)))
        out.append(eu)
    return out


def _starts(college: College, shift_id: str, years: set[int], length: int, teacher_ids: list[str],
            day: str) -> list[int]:
    shift = college.shift(shift_id)
    if length > 1:
        starts = set.intersection(*(set(lab_starts(college, shift_id, y)) for y in years))
    else:
        starts = set.intersection(*(set(available_periods(college, shift_id, y)) for y in years))
    teachers = [college.teacher(t) for t in teacher_ids]
    out = []
    for s in sorted(starts):
        begin = shift.periods[s].start_min
        end = shift.periods[s + length - 1].end_min
        if any(b.day == day and begin < _m(b.end) and _m(b.start) < end for t in teachers for b in t.blocked):
            continue
        out.append(s)
    return out


def _candidate_starts(college: College, u: Unit, day: str) -> list[int]:
    return _starts(college, u.shift_id, u.years, u.length, [u.teacher_id], day)


def _venues_for(college: College, strength: int, kind: Kind, lab_tag: str | None,
                home_department: str) -> list[tuple[str, int]]:
    """(venue_id, cost) pairs; cost = wasted seats (per 10) + borrowing penalty."""
    out = []
    for v in college.venues:
        if v.capacity < strength:
            continue
        if kind == Kind.lab:
            if v.type != VenueType.lab or (lab_tag and lab_tag not in v.tags):
                continue
        elif v.type not in (VenueType.lecture, VenueType.seminar):
            continue
        cost = (v.capacity - strength) // 10
        if v.department_id is not None and v.department_id != home_department:
            cost += W_FOREIGN_ROOM
        out.append((v.id, cost))
    return out


def _candidate_venues(college: College, u: Unit) -> list[tuple[str, int]]:
    return _venues_for(college, u.strength, u.kind, u.lab_tag, u.home_department)


def session_venues(college: College, s: Session, units: dict[str, Unit]) -> list[tuple[str, int]]:
    """Rooms a placed session could use (elective groups size their room by members)."""
    if s.elective_slot_id:
        g = college.elective_group(s.elective_slot_id, s.group_id)
        return _venues_for(college, len(g.student_ids), Kind.lecture, None,
                           college.teacher(g.teacher_id).department_id)
    return _candidate_venues(college, units[s.allotment_id])


def session_groups(college: College, s: Session) -> list[str]:
    """Student groups a session keeps busy. Elective sessions block every participating section."""
    if s.elective_slot_id:
        slot = college.elective_slot(s.elective_slot_id)
        return [g for sid in slot.section_ids for g in group_ids(college.section(sid))]
    if s.batch_id:
        return [s.batch_id]
    return [g for sid in s.section_ids for g in group_ids(college.section(sid))]


def _m(hhmm: str) -> int:
    h, mm = hhmm.split(":")
    return int(h) * 60 + int(mm)


def generate(
    college: College,
    time_limit: float = 30.0,
    workers: int = 8,
    log: bool = False,
    pins: dict[str, list[Pin]] | None = None,
    lunch_pins: dict[tuple[str, str], int] | None = None,
    fixed: list[Session] | None = None,
    keep: Keep | None = None,
) -> Timetable:
    """Build a timetable.

    ``keep`` (mid-semester regenerate): the current placements; every class that leaves its day/time
    is penalised heavily, so the new timetable stays as close to the current one as the new data allows.

    Full generation runs in two stages for speed and quality:
      A. times only (day + period for every class and elective slot), with a room-count
         check so enough suitable rooms are always free;
      B. rooms for the fixed times (room fit, home room, own department first).
    If B can't place every class, the full model (times + rooms) is solved from A's times.

    ``pins`` fix placements per allotment (used by repair); ``fixed`` sessions (elective
    groups during a repair) stay exactly as they are and block their teachers, rooms and
    students. Both use the full model directly.
    """
    t0 = time.perf_counter()
    problems = feasibility.check(college)
    if problems:
        return Timetable(college_id=college.id, status="invalid_input", messages=problems)
    notes = feasibility.warnings(college)
    units = build_units(college)
    eunits = build_elective_units(college)

    def done(tt: Timetable) -> Timetable:
        tt.warnings = notes
        tt.solve_seconds = round(time.perf_counter() - t0, 2)
        return tt

    if pins is not None:
        tt = _solve(college, units, [], time_limit, workers, log, pins, lunch_pins or {}, with_venues=True,
                    blockers=fixed or [])
        if tt.sessions:
            tt.sessions = tt.sessions + list(fixed or [])
        return done(tt)

    stage_a = _solve(college, units, eunits, time_limit * 0.8, workers, log, {}, lunch_pins or {},
                     with_venues=False, keep=keep)
    if not stage_a.sessions:
        return done(stage_a)
    remaining = max(time_limit - (time.perf_counter() - t0), 5.0)
    roomed = assign_rooms(college, units, stage_a.sessions, remaining, workers, keep=keep)
    if roomed is not None:
        stage_a.sessions = roomed
        return done(stage_a)

    # Rare: rooms couldn't be matched to A's times. Keep the elective slots (with rooms of their
    # own), then solve the regular classes' times + rooms together, starting from A.
    electives = assign_rooms(college, units, [s for s in stage_a.sessions if s.elective_slot_id], 10.0, workers,
                             keep=keep)
    if electives is None:
        stage_a.sessions = []
        stage_a.status = "infeasible"
        stage_a.messages = ["The elective groups can't all get a big-enough room at the same time."]
        return done(stage_a)
    hints = {(s.allotment_id, s.day, s.start_period) for s in stage_a.sessions if not s.elective_slot_id}
    lunch = {(ln.section_id, ln.day): ln.period for ln in stage_a.lunches}
    full = _solve(college, units, [], max(remaining, 20.0), workers, log, {}, lunch, with_venues=True,
                  hints=hints, blockers=electives, keep=keep)
    if full.sessions:
        full.sessions = full.sessions + electives
    return done(full)


def _solver(limit: float, workers: int, log: bool) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(limit, 1.0)
    # SOLVER_WORKERS caps the parallel workers (each needs memory): lower it on a small laptop or server.
    solver.parameters.num_search_workers = max(1, min(workers, int(os.environ.get("SOLVER_WORKERS", "8"))))
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
    eunits: list[ElectiveUnit],
    time_limit: float,
    workers: int,
    log: bool,
    pins: dict[str, list[Pin]],
    lunch_pins: dict[tuple[str, str], int],
    with_venues: bool,
    hints: set[tuple[str, str, int]] | None = None,
    blockers: list[Session] | None = None,
    keep: Keep | None = None,
) -> Timetable:
    t0 = time.perf_counter()
    model = cp_model.CpModel()
    days = college.days
    blockers = blockers or []

    def fail(status: str, msg: str) -> Timetable:
        return Timetable(college_id=college.id, status=status, messages=[msg])

    # All period start times (minutes) across every shift: overlap checkpoints.
    checkpoints = sorted({p.start_min for sh in college.shifts for p in sh.periods})

    # Fixed sessions (repairs: elective groups) block their teacher, room and students.
    busy: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)  # (resource, day) -> intervals
    fixed_load: dict[tuple[str, int], int] = defaultdict(int)  # (teacher or group, day index) -> periods
    for b in blockers:
        span = (_m(b.start), _m(b.end))
        busy[(f"t:{b.teacher_id}", b.day)].append(span)
        busy[(f"v:{b.venue_id}", b.day)].append(span)
        fixed_load[(f"t:{b.teacher_id}", days.index(b.day))] += b.length
        for g in session_groups(college, b):
            if span not in busy[(f"g:{g}", b.day)]:
                busy[(f"g:{g}", b.day)].append(span)
                fixed_load[(f"g:{g}", days.index(b.day))] += b.length

    def is_busy(resource: str, day: str, begin: int, end: int) -> bool:
        return any(a < end and begin < z for a, z in busy.get((resource, day), ()))

    # Room classes for the times-only stage: every distinct set of rooms a class could use.
    venue_sets: list[frozenset[str]] = []

    def vset_index(options: list[tuple[str, int]]) -> list[int]:
        vs = frozenset(v for v, _ in options)
        if vs not in venue_sets:
            venue_sets.append(vs)
        return [k for k, S in enumerate(venue_sets) if vs <= S]

    unit_vsets = {ui: frozenset(v for v, _ in _candidate_venues(college, u)) for ui, u in enumerate(units)}
    for vs in list(unit_vsets.values()) + [frozenset(v for v, _ in opts) for eu in eunits for _, opts in eu.rooms]:
        if vs not in venue_sets:
            venue_sets.append(vs)
    subset_of = {ui: [k for k, S in enumerate(venue_sets) if vs <= S] for ui, vs in unit_vsets.items()}

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
                if is_busy(f"t:{u.teacher_id}", day, begin, end) or any(
                    is_busy(f"g:{g}", day, begin, end) for g in u.groups
                ):
                    continue
                rule_cost = _window_rules(college, u.section_ids, day, begin, end)
                if rule_cost is None:  # a Must rule forbids this time
                    continue
                points = [c for c in checkpoints if begin <= c < end]
                for vid, cost in venues:
                    if frozen and not any(
                        p.day == day and p.start == s and p.venue_id in (None, vid) for p in my_pins
                    ):
                        continue
                    if vid is not None and is_busy(f"v:{vid}", day, begin, end):
                        continue
                    var = model.NewBoolVar(f"u{ui}_d{d}_s{s}_{vid}")
                    x[(ui, d, s, vid)] = var
                    if hints is not None:
                        model.AddHint(var, (u.allotment_id, day, s) in hints)
                    if keep is not None:
                        kept = (u.allotment_id, day, s) in keep
                        if hints is None:
                            model.AddHint(var, kept)
                        if not kept:
                            cost_terms.append(W_MOVE * var)
                        elif vid is not None and keep[(u.allotment_id, day, s)] != vid:
                            cost_terms.append(W_ROOM_MOVE * var)
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
                    if cost or rule_cost:
                        cost_terms.append((cost + rule_cost) * var)

    # Elective slots (times-only stage): one variable per day/start; every group meets then.
    z: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for ei, eu in enumerate(eunits):
        shift = college.shift(eu.shift_id)
        group_classes = [vset_index(opts) for _, opts in eu.rooms]
        per_day = []
        for d, day in enumerate(days):
            vars_today = []
            for s in _starts(college, eu.shift_id, eu.years, 1, eu.teacher_ids, day):
                begin, end = shift.periods[s].start_min, shift.periods[s].end_min
                rule_cost = _window_rules(college, eu.slot.section_ids, day, begin, end)
                if rule_cost is None:
                    continue
                var = model.NewBoolVar(f"e{ei}_d{d}_s{s}")
                if rule_cost:
                    cost_terms.append(rule_cost * var)
                if keep is not None:
                    kept = (f"e:{eu.slot.id}", day, s) in keep
                    model.AddHint(var, kept)
                    if not kept:
                        cost_terms.append(W_MOVE * var)
                z[(ei, d, s)] = var
                vars_today.append(var)
                points = [c for c in checkpoints if begin <= c < end]
                for c in points:
                    for t in eu.teacher_ids:
                        cover[(f"t:{t}", d, c)].append(var)
                    for g in eu.groups:
                        cover[(f"g:{g}", d, c)].append(var)
                    for classes in group_classes:  # each group needs one room from its class
                        for k in classes:
                            room_cover[(k, d, c)].append(var)
                for t in eu.teacher_ids:
                    teacher_day[(t, d)].append((var, 1))
                for g in eu.groups:
                    group_day[(g, d)].append((var, 1))
            if len(vars_today) > 1:
                model.AddAtMostOne(vars_today)
            per_day.append(vars_today)
        if sum(1 for v in per_day if v) < eu.count:
            return fail("invalid_input", f"Elective slot '{eu.slot.name}' needs {eu.count} days a week but its "
                        "teachers and sections are free on fewer days.")
        model.Add(sum(v for vs in per_day for v in vs) == eu.count)

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

    # Flexible lunch: every section gets one free period inside its mess window on every day. The
    # period is chosen per section and per day, whatever keeps the days most compact.
    lunch_vars: dict[tuple[str, int], dict[int, cp_model.IntVar]] = {}  # (section, day index) -> period -> var
    for sec in college.sections:
        sh = college.shift(sec.shift_id)
        allowed = set(available_periods(college, sec.shift_id, sec.year))
        cands = [p for p in sh.lunch_candidates() if p in allowed]
        if not cands:
            continue
        for d, day in enumerate(days):
            choice = {p: model.NewBoolVar(f"lunch_{sec.id}_{d}_{p}") for p in cands}
            model.AddExactlyOne(choice.values())
            pin = lunch_pins.get((sec.id, day))
            if pin in choice:
                model.Add(choice[pin] == 1)
            lunch_vars[(sec.id, d)] = choice
            for g in group_ids(sec):
                for p, lv in choice.items():
                    per = sh.periods[p]
                    if is_busy(f"g:{g}", day, per.start_min, per.end_min):
                        model.Add(lv == 0)
                    busy_vars = cover.get((f"g:{g}", d, per.start_min), [])
                    if busy_vars:
                        model.Add(sum(busy_vars) + lv <= 1)

    # Mess split (a Try rule, kind "spread_lunch"): spread each day's lunches evenly over the mess window,
    # weighted by section strength, so half the students eat at 11:30 and half at 12:30 instead of all at once.
    for rule in (r for r in college.rules if r.enabled and r.kind == "spread_lunch"):
        for sh in college.shifts:
            for d in range(len(days)):
                at: dict[int, list] = defaultdict(list)  # period -> strength-weighted lunch choices
                total = 0
                for sec in college.sections:
                    choice = lunch_vars.get((sec.id, d))
                    if sec.shift_id != sh.id or not choice or not rule.applies_to(sec):
                        continue
                    w = max(1, round(sec.strength / 10))  # in tens of students
                    total += w
                    for p, lv in choice.items():
                        at[p].append(w * lv)
                if len(at) < 2:
                    continue
                even = -(-total // len(at))
                over = model.NewIntVar(0, total, "")
                for terms in at.values():
                    model.Add(over >= sum(terms) - even)
                cost_terms.append(W_RULE * rule.weight * over)

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
            load = sum(v * ln for v, ln in items) + fixed_load.get((f"t:{t.id}", d), 0)
            model.Add(load <= t.max_per_day)
            model.Add(peak >= load)
            used = True
        if used:
            cost_terms.append(W_TEACHER_PEAK * peak)

    # Rules: at most N periods a day for the sections in scope.
    for rule in (r for r in college.rules if r.enabled and r.kind == "max_per_day" and r.max_periods):
        for sec in (s for s in college.sections if rule.applies_to(s)):
            for g in group_ids(sec):
                for d in range(len(days)):
                    items = group_day.get((g, d))
                    if not items:
                        continue
                    load = sum(v * ln for v, ln in items) + fixed_load.get((f"g:{g}", d), 0)
                    if rule.mode == "must":
                        model.Add(load <= rule.max_periods)
                    else:
                        extra = model.NewIntVar(0, 50, "")
                        model.Add(extra >= load - rule.max_periods)
                        cost_terms.append(W_RULE * rule.weight * extra)

    # Even student weeks: lighten the heaviest day and avoid single-class days.
    for sec in college.sections:
        max_load = len(available_periods(college, sec.shift_id, sec.year))
        for g in group_ids(sec):
            peak = model.NewIntVar(0, max_load, "")
            for d in range(len(days)):
                items = group_day.get((g, d))
                if not items:
                    continue
                load = sum(v * ln for v, ln in items) + fixed_load.get((f"g:{g}", d), 0)
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
        for g in group_ids(s):
            for d, day in enumerate(days):
                lunch = lunch_vars.get((s.id, d), {})
                # Lunch counts as "occupied" so it never looks like a gap; fixed sessions are occupied too.
                occ = []
                for p in chain:
                    per = shift.periods[p]
                    fixed = 1 if is_busy(f"g:{g}", day, per.start_min, per.end_min) else 0
                    occ.append(sum(cover.get((f"g:{g}", d, per.start_min), [])) + lunch.get(p, 0) + fixed)
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

    def add(**fields) -> None:
        sessions.append(Session(id=f"s{len(sessions) + 1}", **fields))

    for (ui, d, s, vid), var in x.items():
        if not solver.Value(var):
            continue
        u = units[ui]
        shift = college.shift(u.shift_id)
        add(allotment_id=u.allotment_id, subject_id=u.subject_id, teacher_id=u.teacher_id, venue_id=vid or "",
            kind=u.kind, section_ids=u.section_ids, batch_id=u.batch_id, day=days[d], shift_id=u.shift_id,
            start_period=s, length=u.length, start=to_hhmm(shift.periods[s].start_min),
            end=to_hhmm(shift.periods[s + u.length - 1].end_min))

    student_section = {st.id: st.section_id for st in college.students}
    for (ei, d, s), var in z.items():
        if not solver.Value(var):
            continue
        eu = eunits[ei]
        shift = college.shift(eu.shift_id)
        for g in eu.slot.groups:
            secs = sorted({student_section[i] for i in g.student_ids if i in student_section}) or eu.slot.section_ids
            add(allotment_id=f"elective:{eu.slot.id}:{g.id}", subject_id=g.subject_id, teacher_id=g.teacher_id,
                venue_id="", kind=Kind.lecture, section_ids=secs, batch_id=None, day=days[d], shift_id=eu.shift_id,
                start_period=s, length=1, start=to_hhmm(shift.periods[s].start_min),
                end=to_hhmm(shift.periods[s].end_min), elective_slot_id=eu.slot.id, group_id=g.id)

    lunches = []
    for (sec_id, d), choice in lunch_vars.items():
        p = next(p for p, v in choice.items() if solver.Value(v))
        sh = college.shift(college.section(sec_id).shift_id)
        lunches.append(Lunch(shift_id=sh.id, section_id=sec_id, day=days[d], period=p,
                             start=sh.periods[p].start, end=sh.periods[p].end))

    return Timetable(
        college_id=college.id,
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
        sessions=sessions,
        lunches=lunches,
        objective=solver.ObjectiveValue(),
    )


def assign_rooms(
    college: College, units: list[Unit], sessions: list[Session], time_limit: float, workers: int = 8,
    keep: Keep | None = None,
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
        begin, end = _m(s.start), _m(s.end)
        points = [c for c in checkpoints if begin <= c < end]
        options = session_venues(college, s, by_allotment)
        if not options:
            return None
        before = keep.get((s.allotment_id, s.day, s.start_period), "-") if keep is not None else "-"
        for vid, cost in options:
            var = model.NewBoolVar(f"r{i}_{vid}")
            y[(i, vid)] = var
            if before != "-":  # same time as now: prefer the same room
                model.AddHint(var, vid == before)
                if vid != before:
                    cost += W_ROOM_MOVE
            for c in points:
                cover[(vid, s.day, c)].append(var)
            if s.kind == Kind.lecture and not s.elective_slot_id:
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
