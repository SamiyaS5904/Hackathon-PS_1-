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
            if count > len(college.days):
                problems.append(
                    f"{label}: {count} lectures a week but only {len(college.days)} working days, and a subject "
                    "is taught at most one a day."
                )
            ok_venue = any(
                v.type in (VenueType.lecture, VenueType.seminar) and v.capacity >= strength
                for v in college.venues
            )
            if not ok_venue:
                problems.append(f"{label}: no lecture room holds {strength} students.")
        else:
            count, length = subj.labs_per_week, college.lab_periods
            if count > len(college.days):
                problems.append(f"{label}: {count} labs a week but only {len(college.days)} working days "
                                "(at most one a day).")
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

    problems += _room_capacity_problems(college)
    return problems


# ---------------------------------------------------------------------------
# Room capacity: college-wide (hard) and per department (warning).
# ---------------------------------------------------------------------------

def _window_minutes(college: College, shift_ids: set[str]) -> int:
    """Minutes per day covered by the union of these shifts' periods."""
    spans = sorted((p.start_min, p.end_min) for sh in college.shifts if sh.id in shift_ids for p in sh.periods)
    total, cur_s, cur_e = 0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def _room_demand(college: College) -> list[dict]:
    """One row per allotment: what kind of room it needs, for how many minutes a week."""
    rows = []
    for a in college.allotments:
        try:
            subj = college.subject(a.subject_id)
            sections = [college.section(sid) for sid in a.section_ids]
        except StopIteration:
            continue
        shift = college.shift(sections[0].shift_id)
        period_min = sum(p.end_min - p.start_min for p in shift.periods) / max(len(shift.periods), 1)
        if a.batch_id:
            batch = next((b for b in sections[0].batches if b.id == a.batch_id), None)
            strength = batch.strength if batch else 0
        else:
            strength = sum(s.strength for s in sections)
        if a.kind == Kind.lecture:
            periods = subj.lectures_per_week
        else:
            periods = subj.labs_per_week * college.lab_periods
        rows.append({
            "kind": a.kind, "tag": subj.lab_tag if a.kind == Kind.lab else None, "strength": strength,
            "department_id": sections[0].department_id, "shift_id": shift.id,
            "periods": periods, "minutes": periods * period_min,
        })
    return rows


def _fits(v, kind, tag) -> bool:
    if kind == Kind.lab:
        return v.type == VenueType.lab and (tag is None or tag in v.tags)
    return v.type in (VenueType.lecture, VenueType.seminar)


def _room_capacity_problems(college: College) -> list[str]:
    """College-wide: for every group size, are there enough big-enough rooms?

    Rooms can be used in any shift, so supply = rooms x days x minutes covered by all shifts.
    Checked as nested thresholds (groups of 120+ need rooms of 120+, and so on).
    """
    problems = []
    rows = _room_demand(college)
    window = _window_minutes(college, {sh.id for sh in college.shifts}) * len(college.days)
    keys = {(r["kind"], r["tag"]) for r in rows}
    for kind, tag in keys:
        mine = [r for r in rows if r["kind"] == kind and r["tag"] == tag]
        for k in sorted({r["strength"] for r in mine}):
            need = sum(r["minutes"] for r in mine if r["strength"] >= k)
            rooms = [v for v in college.venues if _fits(v, kind, tag) and v.capacity >= k]
            have = len(rooms) * window
            if rooms and need > have:
                what = "lectures" if kind == Kind.lecture else f"labs{f' ({tag})' if tag else ''}"
                problems.append(
                    f"Not enough rooms: {what} for groups of {k}+ students need {need / 60:.0f} hours a week, "
                    f"but rooms that size are only open {have / 60:.0f} hours. Add rooms, split big groups "
                    "or reduce weekly hours."
                )
                break
    return problems


def warnings(college: College) -> list[str]:
    """Not errors, but worth telling the admin before generating."""
    out = []
    rows = _room_demand(college)
    dept_name = {d.id: d.short for d in college.departments}

    # A department needs more lecture-room time than its own rooms give: it will borrow.
    for dept in college.departments:
        mine = [r for r in rows if r["department_id"] == dept.id and r["kind"] == Kind.lecture]
        if not mine:
            continue
        own = [v for v in college.venues if v.department_id == dept.id and _fits(v, Kind.lecture, None)]
        window = _window_minutes(college, {r["shift_id"] for r in mine}) * len(college.days)
        need, have = sum(r["minutes"] for r in mine), len(own) * window
        if need > have:
            out.append(
                f"{dept.short} needs about {need / 60:.0f} lecture-room hours a week but its own rooms give "
                f"{have / 60:.0f}. About {(need - have) / 60:.0f} hours will be placed in shared rooms or "
                "other departments' free rooms."
            )

    # A section is bigger than every room its department owns.
    for s in college.sections:
        own = [v.capacity for v in college.venues if v.department_id == s.department_id
               and _fits(v, Kind.lecture, None)]
        if own and s.strength > max(own):
            out.append(
                f"{s.name} has {s.strength} students but the largest {dept_name.get(s.department_id, '')} room "
                f"holds {max(own)}. Its lectures will use shared or other departments' bigger rooms."
            )
    return out


def group_ids(section) -> list[str]:
    """Student groups that can never be in two places at once.

    A section with batches is modelled as its batches (a whole-section class
    occupies all of them). A section without batches is one group.
    """
    if section.batches:
        return [b.id for b in section.batches]
    return [f"{section.id}:all"]
