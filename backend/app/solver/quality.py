"""Quality score (0-100) for a valid timetable, with an explainable breakdown.

Computed from the finished sessions (not from solver internals) so the UI and
the chatbot can show *why* a timetable scores what it does.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from app.models.domain import College, Kind, Lunch, Session
from app.solver.feasibility import available_periods, group_ids


class QualityItem(BaseModel):
    key: str
    label: str
    value: float
    penalty: float
    detail: str


class QualityReport(BaseModel):
    score: int
    items: list[QualityItem]
    teacher_load: dict[str, dict[str, int]]  # teacher_id -> day -> periods
    venue_utilisation: dict[str, float]  # venue_id -> share of slots used (0..1)


def score(college: College, sessions: list[Session], lunches: list[Lunch] | None = None) -> QualityReport:
    days = college.days
    lunch_at = {(ln.shift_id, ln.year): ln.period for ln in (lunches or [])}

    # Student gaps: empty available periods between a group's first and last class of the day.
    occupied: dict[tuple[str, str], set[int]] = defaultdict(set)
    for s in sessions:
        groups = [s.batch_id] if s.batch_id else [
            g for sid in s.section_ids for g in group_ids(college.section(sid))
        ]
        for g in groups:
            for p in range(s.start_period, s.start_period + s.length):
                occupied[(g, s.day)].add(p)
    total_gaps, n_groups = 0, 0
    for sec in college.sections:
        lp = lunch_at.get((sec.shift_id, sec.year))
        chain = [p for p in available_periods(college, sec.shift_id, sec.year) if p != lp]
        for g in group_ids(sec):
            n_groups += 1
            for d in days:
                used = [i for i, p in enumerate(chain) if p in occupied[(g, d)]]
                if used:
                    total_gaps += (used[-1] - used[0] + 1) - len(used)
    gaps_per_group = total_gaps / max(n_groups, 1)

    # Same subject lecture twice in a day.
    per_day: dict[tuple[str, str], int] = defaultdict(int)
    for s in sessions:
        if s.kind == Kind.lecture:
            per_day[(s.allotment_id, s.day)] += 1
    repeats = sum(n - 1 for n in per_day.values() if n > 1)

    # Teacher load balance: heaviest day minus the even share.
    teacher_load: dict[str, dict[str, int]] = {t.id: {d: 0 for d in days} for t in college.teachers}
    for s in sessions:
        teacher_load[s.teacher_id][s.day] += s.length
    imbalance, n_teachers = 0.0, 0
    for loads in teacher_load.values():
        total = sum(loads.values())
        if total:
            n_teachers += 1
            imbalance += max(loads.values()) - total / len(days)
    imbalance_avg = imbalance / max(n_teachers, 1)

    # Empty seats in lecture rooms.
    waste, n_lect = 0.0, 0
    for s in sessions:
        if s.kind != Kind.lecture:
            continue
        cap = college.venue(s.venue_id).capacity
        strength = sum(college.section(i).strength for i in s.section_ids)
        waste += (cap - strength) / cap
        n_lect += 1
    waste_avg = waste / max(n_lect, 1)

    # Home room: distinct lecture rooms per section (1 = always the same room).
    rooms: dict[str, set[str]] = defaultdict(set)
    for s in sessions:
        if s.kind == Kind.lecture and len(s.section_ids) == 1:
            rooms[s.section_ids[0]].add(s.venue_id)
    rooms_avg = sum(len(v) for v in rooms.values()) / max(len(rooms), 1)

    # Venue utilisation (share of the venue's possible period-slots in use).
    slots_per_day = max(len(sh.periods) for sh in college.shifts) * max(len(college.shifts), 1)
    used: dict[str, int] = defaultdict(int)
    for s in sessions:
        used[s.venue_id] += s.length
    utilisation = {
        v.id: round(min(1.0, used[v.id] / (slots_per_day * len(days))), 3) for v in college.venues
    }

    items = [
        QualityItem(key="gaps", label="Student free gaps", value=round(gaps_per_group, 2),
                    penalty=round(min(30, gaps_per_group * 6), 1),
                    detail=f"{total_gaps} idle periods across {n_groups} student groups per week"),
        QualityItem(key="repeats", label="Same subject twice a day", value=repeats,
                    penalty=round(min(25, repeats * 3), 1),
                    detail=f"{repeats} extra same-day repeats"),
        QualityItem(key="teacher_balance", label="Teacher load balance", value=round(imbalance_avg, 2),
                    penalty=round(min(25, imbalance_avg * 8), 1),
                    detail=f"heaviest day is {imbalance_avg:.1f} periods above an even spread on average"),
        QualityItem(key="room_fit", label="Room size fit", value=round(waste_avg, 3),
                    penalty=round(min(20, waste_avg * 40), 1),
                    detail=f"{waste_avg:.0%} of lecture seats empty on average"),
        QualityItem(key="home_room", label="Room changes for students", value=round(rooms_avg, 2),
                    penalty=round(min(10, (rooms_avg - 1) * 3), 1),
                    detail=f"each section uses {rooms_avg:.1f} lecture rooms on average"),
    ]
    total_penalty = sum(i.penalty for i in items)
    return QualityReport(
        score=max(0, round(100 - total_penalty)),
        items=items,
        teacher_load=teacher_load,
        venue_utilisation=utilisation,
    )
