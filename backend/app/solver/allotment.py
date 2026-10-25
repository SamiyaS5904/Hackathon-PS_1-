"""Teacher allotment suggestions: who should teach which class.

Input (entered by the Department Coordinator): the classes each section needs
(allotments, teacher may be blank) and the subjects each teacher can teach
(``teacher_subjects``, preference 1 = most wanted). The suggestion is a small CP-SAT
model:

  hard  every class gets one teacher who can teach that subject and works in that shift;
        no teacher above their weekly limit (max periods/day x working days), counting
        classes they already teach elsewhere
  soft  fair, even loads (the busiest teacher as light as possible, and nobody who could
        help left idle); preferred subjects; the same teacher for a section's lecture
        and lab of one subject

Nothing is saved: the Coordinator reviews, edits and approves.
"""

from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model
from pydantic import BaseModel

from app.models.domain import Allotment, College, Kind

W_PREFERENCE = 2
W_PEAK = 3
W_SPREAD = 2  # busiest minus least busy teacher who can take one of these classes
W_SPLIT = 2


class Suggestion(BaseModel):
    allotment_id: str
    teacher_id: str | None
    reason: str


class SuggestResult(BaseModel):
    suggestions: list[Suggestion]
    unfilled: list[str]  # plain-language reasons for classes nobody can take
    loads: dict[str, int]  # teacher id -> periods a week after the suggestion


def periods(college: College, a: Allotment) -> int:
    subj = college.subject(a.subject_id)
    return subj.lectures_per_week if a.kind == Kind.lecture else subj.labs_per_week * college.lab_periods


def _label(college: College, a: Allotment) -> str:
    subj = college.subject(a.subject_id)
    secs = " + ".join(college.section(i).name for i in a.section_ids)
    batch = ""
    if a.batch_id:
        batch = " " + next(b.name for b in college.section(a.section_ids[0]).batches if b.id == a.batch_id)
    return f"{subj.name} {'lab' if a.kind == Kind.lab else 'lecture'} ({secs}{batch})"


def suggest(college: College, allotment_ids: list[str], time_limit: float = 10.0) -> SuggestResult:
    """Suggest teachers for the given allotments; every other allotment keeps its teacher."""
    todo = [a for a in college.allotments if a.id in set(allotment_ids)]
    fixed = [a for a in college.allotments if a.id not in set(allotment_ids) and a.teacher_id]
    days = len(college.days)
    cap = {t.id: t.max_per_day * days for t in college.teachers}
    base_load: dict[str, int] = defaultdict(int)
    for a in fixed:
        base_load[a.teacher_id] += periods(college, a)
    for slot in college.elective_slots:
        for g in slot.groups:
            base_load[g.teacher_id] += slot.lectures_per_week

    can = defaultdict(dict)  # subject -> teacher -> preference
    for ts in college.teacher_subjects:
        can[ts.subject_id][ts.teacher_id] = ts.preference

    model = cp_model.CpModel()
    y: dict[tuple[str, str], cp_model.IntVar] = {}
    unfilled: list[str] = []
    for a in todo:
        shift = college.section(a.section_ids[0]).shift_id
        options = [t for t in college.teachers if t.id in can[a.subject_id] and shift in t.shift_ids]
        if not options:
            subj = college.subject(a.subject_id).name
            why = "nobody is listed as able to teach it" if not can[a.subject_id] else \
                "the teachers who can teach it don't work in this shift"
            unfilled.append(f"{_label(college, a)}: {why}. Add {subj} to a teacher's subjects.")
            continue
        for t in options:
            y[(a.id, t.id)] = model.NewBoolVar(f"y_{a.id}_{t.id}")
        model.AddExactlyOne(y[(a.id, t.id)] for t in options)

    cost = []
    load: dict[str, list] = defaultdict(list)
    for (aid, tid), var in y.items():
        a = next(x for x in todo if x.id == aid)
        load[tid].append(periods(college, a) * var)
        cost.append(W_PREFERENCE * (can[a.subject_id][tid] - 1) * var)
    peak = model.NewIntVar(0, max(cap.values(), default=0) or 1, "peak")
    for tid, terms in load.items():
        total = sum(terms) + base_load[tid]
        model.Add(total <= cap[tid])
        model.Add(peak >= total)
    cost.append(W_PEAK * peak)
    low = model.NewIntVar(0, max(cap.values(), default=0) or 1, "low")
    for tid, terms in load.items():
        model.Add(low <= sum(terms) + base_load[tid])
    cost.append(W_SPREAD * (peak - low))

    # Same teacher for a section's lecture and labs of one subject where possible.
    by_subject_section = defaultdict(list)
    for a in todo:
        by_subject_section[(a.subject_id, tuple(sorted(a.section_ids)))].append(a)
    for group in by_subject_section.values():
        for a, b in zip(group, group[1:]):
            for t in college.teachers:
                if (a.id, t.id) in y and (b.id, t.id) in y:
                    split = model.NewBoolVar("")
                    model.Add(split >= y[(a.id, t.id)] - y[(b.id, t.id)])
                    cost.append(W_SPLIT * split)

    model.Minimize(sum(cost))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model) if y else cp_model.OPTIMAL
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SuggestResult(
            suggestions=[Suggestion(allotment_id=a.id, teacher_id=None, reason="") for a in todo],
            unfilled=unfilled + ["The listed teachers don't have enough free periods for all these classes. "
                                 "Raise a teacher's daily limit or add more teachers to these subjects."],
            loads={},
        )

    final = dict(base_load)
    chosen: dict[str, str] = {}
    for (aid, tid), var in y.items():
        if solver.Value(var):
            chosen[aid] = tid
            final[tid] = final.get(tid, 0) + periods(college, next(x for x in todo if x.id == aid))
    names = {t.id: t.name for t in college.teachers}
    out = []
    for a in todo:
        tid = chosen.get(a.id)
        if tid is None:
            out.append(Suggestion(allotment_id=a.id, teacher_id=None, reason="No suitable teacher"))
            continue
        pref = can[a.subject_id][tid]
        choice = {1: "1st choice", 2: "2nd choice"}.get(pref, f"choice {pref}")
        out.append(Suggestion(allotment_id=a.id, teacher_id=tid,
                              reason=f"{names[tid]}: {choice} subject · {final[tid]}/{cap[tid]} periods a week"))
    return SuggestResult(suggestions=out, unfilled=unfilled, loads=final)
