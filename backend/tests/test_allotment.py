"""Teacher allotment suggestions."""

from app.models.domain import Teacher, TeacherSubject
from app.solver import feasibility
from app.solver.allotment import suggest
from tests.conftest import tiny_college


def blank(college, ids):
    for a in college.allotments:
        if a.id in ids:
            a.teacher_id = None


def test_classes_without_teacher_block_generation():
    c = tiny_college()
    blank(c, {"a1"})
    assert any("no teacher yet" in p for p in feasibility.check(c))


def test_suggestion_prefers_first_choice_and_fills_everything():
    c = tiny_college()
    c.teachers.append(Teacher(id="t3", name="Dr. C", department_id="cse", shift_ids=["day"], max_per_day=4))
    c.teacher_subjects = [
        TeacherSubject(teacher_id="t1", subject_id="maths", preference=2),
        TeacherSubject(teacher_id="t3", subject_id="maths", preference=1),
        TeacherSubject(teacher_id="t2", subject_id="prog", preference=1),
    ]
    blank(c, {"a1", "a2", "a3", "a4"})
    r = suggest(c, ["a1", "a2", "a3", "a4"])
    got = {s.allotment_id: s.teacher_id for s in r.suggestions}
    assert got["a1"] == "t3"  # 1st choice for maths
    assert got["a2"] == got["a3"] == got["a4"] == "t2"  # same teacher for programming lecture + labs
    assert r.unfilled == [] and all("periods a week" in s.reason for s in r.suggestions)


def test_weekly_limit_moves_work_to_another_teacher():
    c = tiny_college()
    c.teachers.append(Teacher(id="t3", name="Dr. C", department_id="cse", shift_ids=["day"], max_per_day=4))
    c.teachers[0].max_per_day = 1  # Dr. A: only 3 periods a week (3 days)
    c.teacher_subjects = [TeacherSubject(teacher_id="t1", subject_id="prog", preference=1),
                          TeacherSubject(teacher_id="t3", subject_id="prog", preference=2)]
    blank(c, {"a2", "a3", "a4"})  # programming: 2 lectures + 2 labs of 2 periods = 6 periods
    r = suggest(c, ["a2", "a3", "a4"])
    # Dr. A already teaches maths (3 periods) = their whole weekly limit, so Dr. C takes programming.
    assert all(s.teacher_id == "t3" for s in r.suggestions)
    assert r.loads["t1"] == 3 and r.loads["t3"] == 6


def test_unfillable_class_is_explained():
    c = tiny_college()
    c.teacher_subjects = []
    blank(c, {"a1"})
    r = suggest(c, ["a1"])
    assert r.suggestions[0].teacher_id is None
    assert r.unfilled and "Add Maths to a teacher's subjects" in r.unfilled[0]


def test_nobody_who_could_help_is_left_idle():
    c = tiny_college()
    c.teachers.append(Teacher(id="t3", name="Dr. C", department_id="cse", shift_ids=["day"], max_per_day=4))
    c.teachers[0].max_per_day = 5  # Dr. A could take everything (9 periods) within the weekly limit
    c.teacher_subjects = [TeacherSubject(teacher_id="t1", subject_id="maths", preference=1),
                          TeacherSubject(teacher_id="t1", subject_id="prog", preference=1),
                          TeacherSubject(teacher_id="t3", subject_id="prog", preference=2)]
    blank(c, {"a1", "a2", "a3", "a4"})
    r = suggest(c, ["a1", "a2", "a3", "a4"])
    # Fair share beats Dr. A's preference: Dr. C takes part of programming instead of sitting idle.
    assert r.loads["t3"] >= 4 and abs(r.loads["t1"] - r.loads["t3"]) <= 2
    assert r.loads["t1"] + r.loads["t3"] == 9
