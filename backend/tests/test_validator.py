"""The validator must catch every kind of hard-rule violation."""

from app.models.domain import Kind, Lunch, Session
from app.validator.check import validate


def sess(sid, allot, subj, teacher, venue, kind, day, start, length=1, batch=None):
    starts = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00"]
    ends = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    return Session(
        id=sid, allotment_id=allot, subject_id=subj, teacher_id=teacher, venue_id=venue, kind=kind,
        section_ids=["s1"], batch_id=batch, day=day, shift_id="day", start_period=start, length=length,
        start=starts[start], end=ends[start + length - 1],
    )


LUNCH = [Lunch(shift_id="day", year=1, period=3, start="12:00", end="13:00")]


def valid_sessions():
    L, B = Kind.lecture, Kind.lab
    return [
        sess("m1", "a1", "maths", "t1", "r1", L, "Mon", 0),
        sess("m2", "a1", "maths", "t1", "r1", L, "Tue", 0),
        sess("m3", "a1", "maths", "t1", "r1", L, "Wed", 0),
        sess("p1", "a2", "prog", "t2", "r1", L, "Mon", 1),
        sess("p2", "a2", "prog", "t2", "r1", L, "Tue", 1),
        sess("l1", "a3", "prog", "t2", "lab", B, "Wed", 1, 2, "b1"),
        sess("l2", "a4", "prog", "t2", "lab", B, "Mon", 4, 2, "b2"),
    ]


def types(college, sessions, lunches=LUNCH):
    return {v.type for v in validate(college, sessions, lunches)}


def test_valid_timetable_has_no_violations(college):
    assert validate(college, valid_sessions(), LUNCH) == []


def test_teacher_clash(college):
    s = valid_sessions()
    s[3] = sess("p1", "a2", "prog", "t2", "r1", Kind.lecture, "Wed", 1)  # t2 already in lab Wed 10-12
    assert "teacher_clash" in types(college, s)


def test_venue_clash(college):
    s = valid_sessions()
    s[3] = sess("p1", "a2", "prog", "t2", "r1", Kind.lecture, "Mon", 0)  # r1 has maths Mon 9-10
    t = types(college, s)
    assert "venue_clash" in t and "student_clash" in t


def test_whole_section_class_clashes_with_batch_lab(college):
    s = valid_sessions()
    s[0] = sess("m1", "a1", "maths", "t1", "r1", Kind.lecture, "Mon", 4)  # B2 lab Mon 13-15
    assert "student_clash" in types(college, s)


def test_lab_in_lecture_room_and_lecture_in_lab(college):
    s = valid_sessions()
    s[5] = sess("l1", "a3", "prog", "t2", "r1", Kind.lab, "Wed", 1, 2, "b1")
    s[0] = sess("m1", "a1", "maths", "t1", "lab", Kind.lecture, "Mon", 0)
    t = types(college, s)
    assert "venue_type" in t and "venue_too_small" in t


def test_wrong_weekly_count(college):
    assert "wrong_count" in types(college, valid_sessions()[1:])


def test_class_during_lunch_and_missing_lunch(college):
    s = valid_sessions()
    s[1] = sess("m2", "a1", "maths", "t1", "r1", Kind.lecture, "Tue", 3)  # 12-13 is lunch
    assert "class_during_lunch" in types(college, s)
    assert "lunch_missing" in types(college, valid_sessions(), lunches=[])


def test_lab_split_across_break(college):
    periods = list(college.shifts[0].periods)
    periods[2] = periods[2].model_copy(update={"end": "11:50"})  # gap 11:50-12:00
    college.shifts[0].periods = periods
    s = valid_sessions()
    s[5] = sess("l1", "a3", "prog", "t2", "lab", Kind.lab, "Wed", 2, 2, "b1")
    s[5].end = "13:00"
    assert "split_block" in types(college, s)


def test_teacher_overload(college):
    college.teachers[1].max_per_day = 2
    assert "teacher_overload" in types(college, valid_sessions())  # t2 Mon: 1 lecture + 2-period lab
