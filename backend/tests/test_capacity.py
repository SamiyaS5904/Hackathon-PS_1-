"""Edge cases around room capacity and departments sharing rooms."""

from app.models.domain import Allotment, Department, Kind, Section, Subject, Teacher, Venue, VenueType
from app.solver import feasibility
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college


def crowded_cse():
    """CSE owns one lecture room but has 4 sections; a shared hall and an ME room exist."""
    college = tiny_college()
    college.departments.append(Department(id="me", name="Mechanical", short="ME"))
    college.venues += [
        Venue(id="hall", name="Seminar Hall", type=VenueType.seminar, capacity=100),
        Venue(id="me1", name="ME Room", type=VenueType.lecture, capacity=45, department_id="me"),
    ]
    for i in (2, 3, 4):
        college.sections.append(
            Section(id=f"s{i}", name=f"CSE-1{'ABCD'[i - 1]}", department_id="cse", year=1, strength=40, shift_id="day")
        )
        college.teachers.append(Teacher(id=f"t{i + 1}", name=f"Dr. {i}", department_id="cse", shift_ids=["day"]))
        college.allotments.append(
            Allotment(id=f"x{i}", subject_id="maths", teacher_id=f"t{i + 1}", kind=Kind.lecture, section_ids=[f"s{i}"])
        )
        college.subjects.append(
            Subject(id=f"oop{i}", code=f"OOP{i}", name=f"OOP {i}", department_id="cse", year=1, lectures_per_week=3)
        )
        college.allotments.append(
            Allotment(id=f"y{i}", subject_id=f"oop{i}", teacher_id=f"t{i + 1}", kind=Kind.lecture, section_ids=[f"s{i}"])
        )
    return college


def test_department_overflow_borrows_other_rooms_and_warns():
    college = crowded_cse()
    notes = feasibility.warnings(college)
    assert any("CSE needs about" in n and "other departments' free rooms" in n for n in notes)

    tt = generate(college, time_limit=15)
    assert tt.status in ("optimal", "feasible"), tt.messages
    assert validate(college, tt.sessions, tt.lunches) == []
    used = {s.venue_id for s in tt.sessions if s.kind == Kind.lecture}
    assert used & {"hall", "me1"}, "overflow lectures should go to shared / other departments' rooms"
    assert tt.warnings


def test_section_bigger_than_own_rooms_uses_bigger_shared_room():
    college = tiny_college()
    college.sections[0].strength = 60
    college.sections[0].batches[0].strength = 30
    college.sections[0].batches[1].strength = 30
    college.venues[1].capacity = 30  # lab fits a batch of 30
    college.venues.append(Venue(id="hall", name="Seminar Hall", type=VenueType.seminar, capacity=80))
    assert any("largest CSE room holds 45" in n for n in feasibility.warnings(college))

    tt = generate(college, time_limit=10)
    assert validate(college, tt.sessions, tt.lunches) == []
    assert all(s.venue_id == "hall" for s in tt.sessions if s.kind == Kind.lecture)


def test_section_bigger_than_every_room_is_an_error():
    college = tiny_college()
    college.sections[0].strength = 90
    college.sections[0].batches[0].strength = 45
    college.sections[0].batches[1].strength = 45
    tt = generate(college, time_limit=5)
    assert tt.status == "invalid_input"
    assert any("no lecture room holds 90" in m for m in tt.messages)


def test_not_enough_big_room_time_college_wide_is_an_error():
    college = tiny_college()
    # Four 80-student combined groups need 24 big-hall periods; one hall is open 18 periods (3 days x 6).
    college.venues.append(Venue(id="hall", name="Hall", type=VenueType.seminar, capacity=90))
    college.sections += [
        Section(id=f"c{i}", name=f"C{i}", department_id="cse", year=1, strength=40, shift_id="day") for i in range(8)
    ]
    for i in range(8):
        college.subjects.append(Subject(id=f"big{i}", code=f"B{i}", name=f"Big {i}", department_id="cse", year=1,
                                        lectures_per_week=3))
        college.teachers.append(Teacher(id=f"bt{i}", name=f"Prof {i}", department_id="cse", shift_ids=["day"]))
    for i, pair in enumerate((["c0", "c1"], ["c2", "c3"], ["c4", "c5"], ["c6", "c7"])):
        for j in range(2):
            college.allotments.append(Allotment(id=f"big{i}{j}", subject_id=f"big{i * 2 + j}", teacher_id=f"bt{i * 2 + j}",
                                                kind=Kind.lecture, section_ids=pair))
    problems = feasibility.check(college)
    assert any(p.startswith("Not enough rooms: lectures for groups of 80+") for p in problems), problems


def test_more_lectures_than_working_days_is_an_error():
    college = tiny_college()
    college.subjects[0].lectures_per_week = 4  # 3 working days, max one lecture of a subject per day
    problems = feasibility.check(college)
    assert any("at most one a day" in p for p in problems), problems
