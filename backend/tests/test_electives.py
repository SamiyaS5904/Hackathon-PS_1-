"""Elective slots and pooled cross-department groups."""

from app.accounts import Member
from app.edits.moves import move_options, repair_move
from app.models.domain import (
    Department,
    ElectiveGroup,
    ElectiveSlot,
    Section,
    Student,
    Subject,
    Teacher,
    Venue,
    VenueType,
)
from app.permissions import visible_sessions
from app.solver import feasibility
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college


def elective_college(**slot_overrides):
    """CSE-1A (tiny college) + ME-1A, both in an elective slot with a CSE-taught and an ME-taught group."""
    c = tiny_college()
    c.departments.append(Department(id="me", name="Mechanical", short="ME"))
    c.sections.append(Section(id="m1", name="ME-1A", department_id="me", year=1, strength=30, shift_id="day"))
    c.venues += [
        Venue(id="me-room", name="ME Room", type=VenueType.lecture, capacity=40, department_id="me"),
        Venue(id="hall", name="Hall", type=VenueType.seminar, capacity=80),
    ]
    c.teachers += [
        Teacher(id="t-me", name="Dr. ME", department_id="me", shift_ids=["day"]),
        Teacher(id="t-cs", name="Dr. CS", department_id="cse", shift_ids=["day"]),
    ]
    c.subjects += [
        Subject(id="rob", code="ROB", name="Robotics", department_id="me", year=1),
        Subject(id="ai", code="AI", name="AI Basics", department_id="cse", year=1),
    ]
    c.students = [Student(id=f"s1-{i}", roll_no=f"A{i}", name=f"A{i}", email=f"a{i}@x.edu", section_id="s1",
                          batch_id="b1" if i <= 20 else "b2") for i in range(1, 41)]
    c.students += [Student(id=f"m1-{i}", roll_no=f"M{i}", name=f"M{i}", email=f"m{i}@x.edu", section_id="m1")
                   for i in range(1, 31)]
    a_ids, m_ids = [s.id for s in c.students if s.section_id == "s1"], [s.id for s in c.students if s.section_id == "m1"]
    slot = dict(
        id="oe", name="Open Elective", section_ids=["s1", "m1"], lectures_per_week=2,
        groups=[
            # Pooled across departments: each group mixes CSE and ME students.
            ElectiveGroup(id="rob", name="Robotics", subject_id="rob", teacher_id="t-me",
                          student_ids=a_ids[:15] + m_ids[:15]),
            ElectiveGroup(id="ai", name="AI Basics", subject_id="ai", teacher_id="t-cs",
                          student_ids=a_ids[15:] + m_ids[15:]),
        ],
    )
    slot.update(slot_overrides)
    c.elective_slots = [ElectiveSlot(**slot)]
    return c


def test_elective_groups_meet_together_in_fitting_rooms():
    c = elective_college()
    tt = generate(c, time_limit=10)
    assert tt.status in ("optimal", "feasible"), tt.messages
    assert validate(c, tt.sessions, tt.lunches) == []
    el = [s for s in tt.sessions if s.elective_slot_id]
    assert len(el) == 2 * 2  # 2 groups x 2 meetings
    times = {g: sorted((s.day, s.start_period) for s in el if s.group_id == g) for g in ("rob", "ai")}
    assert times["rob"] == times["ai"]
    rob_rooms = {s.venue_id for s in el if s.group_id == "rob"}
    assert rob_rooms == {"me-room"}  # 30 members, ME teacher -> ME room preferred
    # Home sections (including every lab batch) have nothing else at elective times.
    for s in tt.sessions:
        if s.elective_slot_id or not set(s.section_ids) & {"s1", "m1"}:
            continue
        for day, p in times["rob"]:
            assert not (s.day == day and s.start_period <= p < s.start_period + s.length), s


def test_membership_problems_are_reported():
    c = elective_college()
    g0, g1 = c.elective_slots[0].groups
    g1.student_ids.append(g0.student_ids[0])  # one student in two groups
    probs = feasibility.check(c)
    assert any("is in both" in p for p in probs), probs

    c = elective_college()
    c.elective_slots[0].groups[1].student_ids.pop()  # one student in no group
    assert any("aren't in any group" in p for p in feasibility.check(c))

    c = elective_college()
    c.elective_slots[0].groups[1].teacher_id = "t-me"  # one teacher, two parallel groups
    assert any("teaches both" in p for p in feasibility.check(c))


def test_validator_catches_split_elective_times():
    c = elective_college()
    tt = generate(c, time_limit=10)
    el = [s for s in tt.sessions if s.elective_slot_id and s.group_id == "ai"]
    other_day = next(d for d in c.days if d not in {s.day for s in el})
    moved = el[0].model_copy(update={"day": other_day})
    broken = [moved if s.id == el[0].id else s for s in tt.sessions]
    assert "elective_split" in {v.type for v in validate(c, broken, tt.lunches)}


def test_repair_keeps_electives_fixed():
    c = elective_college()
    tt = generate(c, time_limit=10)
    regular = next(s for s in tt.sessions if not s.elective_slot_id and s.kind.value == "lecture")
    assert all(o.status == "blocked" for o in move_options(c, tt, next(s.id for s in tt.sessions if s.elective_slot_id)))
    for o in move_options(c, tt, regular.id):
        if o.status == "blocked":
            continue
        new, msg = repair_move(c, tt, regular.id, o.day, o.start_period)
        if new is None:
            continue
        assert validate(c, new.sessions, new.lunches) == []
        before = sorted((s.id, s.day, s.start_period, s.venue_id) for s in tt.sessions if s.elective_slot_id)
        after = sorted((s.id, s.day, s.start_period, s.venue_id) for s in new.sessions if s.elective_slot_id)
        assert before == after
        return
    raise AssertionError("expected at least one possible move")


def test_student_sees_only_own_elective_group():
    c = elective_college()
    tt = generate(c, time_limit=10)
    m = Member(user_id="u", org_id="o", org_name="O", name="A1", email="a1@x.edu", role="student",
               section_id="s1", batch_id="b1")
    mine = [s for s in visible_sessions(m, c, tt) if s.elective_slot_id]
    assert mine and {s.group_id for s in mine} == {"rob"}  # a1 is in Robotics
