"""The solver must always produce timetables the independent validator accepts."""

from app.models.domain import Kind, Period, Section, Shift, Teacher, TimeBlock
from app.seed.demo_college import build_demo_college
from app.solver.generate import generate
from app.solver.quality import score
from app.validator.check import validate
from tests.conftest import tiny_college


def assert_valid(college, tt):
    assert tt.status in ("optimal", "feasible"), tt.messages
    violations = validate(college, tt.sessions, tt.lunches)
    assert violations == [], [v.message for v in violations]


def test_tiny_college_is_valid(college):
    tt = generate(college, time_limit=10)
    assert_valid(college, tt)
    assert len(tt.sessions) == 3 + 2 + 1 + 1
    assert 0 <= score(college, tt.sessions, tt.lunches).score <= 100


def test_teacher_blocked_time_is_respected():
    college = tiny_college()
    college.teachers[0].blocked = [TimeBlock(day=d, start="09:00", end="11:00") for d in college.days]
    tt = generate(college, time_limit=10)
    assert_valid(college, tt)
    assert all(s.start >= "11:00" for s in tt.sessions if s.teacher_id == "t1")


def test_two_overlapping_shifts_share_venue_and_teacher():
    college = tiny_college()
    late = Shift(id="late", name="Late", periods=[
        Period(start="10:30", end="11:30"), Period(start="11:30", end="12:30"), Period(start="12:30", end="13:30"),
    ])
    college.shifts.append(late)
    college.sections.append(Section(id="s2", name="CSE-2A", department_id="cse", year=2, strength=40, shift_id="late"))
    college.teachers[0].shift_ids = ["day", "late"]
    college.teachers[0].max_per_day = 6
    from app.models.domain import Allotment, Subject
    college.subjects.append(Subject(id="dsa", code="DS", name="DSA", department_id="cse", year=2, lectures_per_week=3))
    college.allotments.append(Allotment(id="a9", subject_id="dsa", teacher_id="t1", kind=Kind.lecture, section_ids=["s2"]))
    tt = generate(college, time_limit=10)
    assert_valid(college, tt)  # validator checks time overlap across shifts for r1 and t1


def test_impossible_input_is_explained_not_solved():
    college = tiny_college()
    college.subjects[0].lectures_per_week = 30  # far more than 3 days can hold
    tt = generate(college, time_limit=5)
    assert tt.status == "invalid_input"
    assert any("needs" in m for m in tt.messages)


def test_teacher_in_wrong_shift_is_reported():
    college = tiny_college()
    college.teachers[0] = Teacher(id="t1", name="Dr. A", department_id="cse", shift_ids=["night"])
    tt = generate(college, time_limit=5)
    assert tt.status == "invalid_input"


def test_lunch_window_without_full_period_is_reported():
    college = tiny_college()
    college.shifts[0].lunch.window_end = "12:30"
    tt = generate(college, time_limit=5)
    assert tt.status == "invalid_input"
    assert any("mess window" in m for m in tt.messages)


def test_demo_college_is_clash_free():
    college = build_demo_college()
    tt = generate(college, time_limit=30)
    assert_valid(college, tt)
    # Lunch for every section on every working day (chosen per section and per day).
    assert {(ln.section_id, ln.day) for ln in tt.lunches} == {
        (s.id, d) for s in college.sections if college.shift(s.shift_id).lunch for d in college.days}
