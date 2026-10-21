"""Pre-solve checks that catch impossible input early, in plain language.

If any of these fail, the solver is never started: the admin gets a list of
concrete problems ("CSE-3A needs 34 periods but only 30 are available") instead
of a vague "no solution".
"""

from __future__ import annotations

from collections import defaultdict

from app.models.domain import College, Kind, VenueType


def available_periods(college: College, shift_id: str, year: int) -> list[int]:
    """Indices of periods in a shift that are not covered by a year-specific break."""
    shift = college.shift(shift_id)
    out = []
    for i, p in enumerate(shift.periods):
        blocked = any(
            year in b.years
            and p.start_min < _m(b.end)
            and _m(b.start) < p.end_min
            for b in shift.year_breaks
        )
        if not blocked:
            out.append(i)
    return out


def lab_starts(college: College, shift_id: str, year: int) -> list[int]:
    """Period indices where a full lab block (college lab length) can start."""
    shift = college.shift(shift_id)
    avail = set(available_periods(college, shift_id, year))
    length = college.lab_periods
    starts = []
    for s in range(len(shift.periods) - length + 1):
        idx = range(s, s + length)
        if not all(i in avail for i in idx):
            continue
        if all(shift.periods[i].end == shift.periods[i + 1].start for i in range(s, s + length - 1)):
            starts.append(s)
    return starts


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def check(college: College) -> list[str]:
    problems: list[str] = []
    ids = {
        "section": {s.id for s in college.sections},
        "teacher": {t.id for t in college.teachers},
        "subject": {s.id for s in college.subjects},
        "shift": {s.id for s in college.shifts},
        "department": {d.id for d in college.departments},
    }

    for s in college.sections:
        if s.shift_id not in ids["shift"]:
            problems.append(f"Section {s.name} uses an unknown shift '{s.shift_id}'.")
        if s.batches and sum(b.strength for b in s.batches) != s.strength:
            problems.append(f"Section {s.name}: batch strengths don't add up to {s.strength} students.")
    for t in college.teachers:
        for sh in t.shift_ids:
            if sh not in ids["shift"]:
                problems.append(f"Teacher {t.name} is set to an unknown shift '{sh}'.")
    for sh in college.shifts:
        if sh.lunch and not sh.lunch_candidates():
            problems.append(
                f"{sh.name} shift: the mess window {sh.lunch.window_start}-{sh.lunch.window_end} "
                "doesn't contain a full period, so lunch can't be placed."
            )
    if problems:
        return problems

    # Per-allotment checks + demand per resource.
    group_demand: dict[str, int] = defaultdict(int)  # batch-resource -> periods needed
    teacher_demand: dict[str, int] = defaultdict(int)
    for a in college.allotments:
        if a.subject_id not in ids["subject"]:
            problems.append(f"Allotment {a.id} refers to an unknown subject.")
            continue
        if a.teacher_id not in ids["teacher"]:
            problems.append(f"Allotment {a.id} refers to an unknown teacher.")
            continue
        missing = [sid for sid in a.section_ids if sid not in ids["section"]]
        if missing:
            problems.append(f"Allotment {a.id} refers to unknown section(s) {', '.join(missing)}.")
            continue

        subj = college.subject(a.subject_id)
        teacher = college.teacher(a.teacher_id)
        sections = [college.section(sid) for sid in a.section_ids]
        label = f"{subj.name} ({', '.join(s.name for s in sections)})"

        shifts = {s.shift_id for s in sections}
        if len(shifts) > 1:
            problems.append(f"{label}: combined sections are in different shifts, so they can never meet together.")
            continue
        shift_id = shifts.pop()
        if shift_id not in teacher.shift_ids:
            problems.append(
                f"{label}: {teacher.name} doesn't teach in the {college.shift(shift_id).name} shift."
            )

        if a.batch_id:
            batch = next((b for b in sections[0].batches if b.id == a.batch_id), None)
            if batch is None:
                problems.append(f"{label}: batch '{a.batch_id}' is not part of {sections[0].name}.")
                continue
            strength = batch.strength
            groups = [batch.id]
        else:
            strength = sum(s.strength for s in sections)
            groups = [g for s in sections for g in group_ids(s)]

        if a.kind == Kind.lecture:
            count, length = subj.lectures_per_week, 1
            ok_venue = any(
                v.type in (VenueType.lecture, VenueType.seminar) and v.capacity >= strength
                for v in college.venues
            )
            if not ok_venue:
                problems.append(f"{label}: no lecture room holds {strength} students.")
        else:
            count, length = subj.labs_per_week, college.lab_periods
            ok_venue = any(
                v.type == VenueType.lab
                and v.capacity >= strength
                and (subj.lab_tag is None or subj.lab_tag in v.tags)
                for v in college.venues
            )
            if not ok_venue:
                tag = f" with '{subj.lab_tag}'" if subj.lab_tag else ""
                problems.append(f"{label}: no lab{tag} holds {strength} students.")
            years = {s.year for s in sections}
            if not all(lab_starts(college, shift_id, y) for y in years):
                problems.append(
                    f"{label}: the {college.shift(shift_id).name} shift has no {college.lab_periods} "
                    "back-to-back periods without a break, so labs can't fit."
                )

        for g in groups:
            group_demand[g] += count * length
        teacher_demand[a.teacher_id] += count * length

    # Capacity per student group.
    for s in college.sections:
        lunch = 1 if college.shift(s.shift_id).lunch else 0
        capacity = len(college.days) * (len(available_periods(college, s.shift_id, s.year)) - lunch)
        for g in group_ids(s):
            need = group_demand.get(g, 0)
            if need > capacity:
                who = s.name if g.endswith(":all") else f"{s.name} batch {g.split(':')[-1]}"
                problems.append(f"{who} needs {need} periods a week but only {capacity} are available.")

    # Capacity per teacher.
    for t in college.teachers:
        need = teacher_demand.get(t.id, 0)
        cap = t.max_per_day * len(college.days)
        if need > cap:
            problems.append(
                f"{t.name} has {need} periods a week but the limit is {t.max_per_day}/day "
                f"({cap}/week). Raise the limit or move some classes to another teacher."
            )

    return problems


def group_ids(section) -> list[str]:
    """Student groups that can never be in two places at once.

    A section with batches is modelled as its batches (a whole-section class
    occupies all of them). A section without batches is one group.
    """
    if section.batches:
        return [b.id for b in section.batches]
    return [f"{section.id}:all"]
