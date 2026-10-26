"""Teacher booking: office hours, doubt slots, meetings, and clash flags after timetable changes."""

import pytest

from app import bookings
from app.bookings import OfficeHour
from app.db.models import init_db
from app.models.domain import Holiday, Override, Student
from app.solver.generate import generate
from tests.conftest import tiny_college

TODAY, NOW = "2026-11-01", "10:00"  # a Sunday; the tiny college works Mon-Wed
MON, TUE = "2026-11-02", "2026-11-03"
WEEKDAY_OF = {"Mon": MON, "Tue": TUE, "Wed": "2026-11-04"}


@pytest.fixture(scope="module")
def world():
    init_db()
    students = [Student(id=f"st{i}", roll_no=str(i), name=f"Student {i}", email=f"st{i}@x.edu", section_id="s1",
                        batch_id="b1" if i % 2 else "b2") for i in range(1, 4)]
    c = tiny_college(students=students, holidays=[Holiday(date="2026-11-09", label="Diwali")])
    return c, generate(c, time_limit=10)


def _free(c, tt, teacher_id: str, *students: Student):
    """A (day, period index) where the teacher and every given student have no class."""
    shift = c.shifts[0]
    for day in c.days:
        for i, p in enumerate(shift.periods):
            busy = [s for s in tt.sessions if s.day == day and bookings._overlaps(s.start, s.end, p.start, p.end)
                    and (s.teacher_id == teacher_id
                         or any(s in bookings.student_classes(c, tt.sessions, st) for st in students))]
            if not busy:
                return day, i
    raise AssertionError("no common free period")


def _hour(org, c, tt, seats=2):
    day, i = _free(c, tt, "t1", *c.students)  # every student can book it (they are in different lab batches)
    p = c.shifts[0].periods[i]
    h = OfficeHour(teacher_id="t1", day=day, start=p.start, end=p.end, seats=seats, place="Staff room")
    assert bookings.add_office_hour(c, tt, org, h) is None
    return h


def test_office_hours_never_overlap_the_teachers_own_classes(world):
    c, tt = world
    s = next(s for s in tt.sessions if s.teacher_id == "t1")
    clash = OfficeHour(teacher_id="t1", day=s.day, start=s.start, end=s.end)
    assert "You teach" in bookings.add_office_hour(c, tt, "bk-hours", clash)
    h = _hour("bk-hours", c, tt)
    again = OfficeHour(teacher_id="t1", day=h.day, start=h.start, end=h.end)
    assert "already have office hours" in bookings.add_office_hour(c, tt, "bk-hours", again)
    assert "isn't a working day" in bookings.add_office_hour(c, tt, "bk-hours", OfficeHour(
        teacher_id="t1", day="Sun", start="10:00", end="11:00"))


def test_doubt_slots_fill_up_and_skip_holidays_and_own_classes(world):
    c, tt = world
    org = "bk-doubt"
    h = _hour(org, c, tt, seats=2)
    s1, s2, s3 = c.students
    slots = bookings.doubt_slots(c, tt, org, s1, TODAY, NOW)
    dates = [x.date for x in slots]
    assert WEEKDAY_OF[h.day] in dates and "2026-11-09" not in dates  # holiday has no slots
    assert all(x.seats_left == 2 for x in slots)
    d = WEEKDAY_OF[h.day]
    b1, msg = bookings.book_doubt(c, tt, org, s1, h.id, d, "Recursion", "u1", s1.name, TODAY, NOW)
    assert b1 is not None and "Booked" in msg
    assert d not in [x.date for x in bookings.doubt_slots(c, tt, org, s1, TODAY, NOW)]  # already booked it
    assert next(x for x in bookings.doubt_slots(c, tt, org, s2, TODAY, NOW) if x.date == d).seats_left == 1
    assert bookings.book_doubt(c, tt, org, s2, h.id, d, "", "u2", s2.name, TODAY, NOW)[0] is not None
    assert d not in [x.date for x in bookings.doubt_slots(c, tt, org, s3, TODAY, NOW)]  # full
    full, why = bookings.book_doubt(c, tt, org, s3, h.id, d, "", "u3", s3.name, TODAY, NOW)
    assert full is None and "full" in why
    late, why = bookings.book_doubt(c, tt, org, s3, h.id, d, "", "u3", s3.name, d, "23:00")
    assert late is None and "passed" in why
    # The teacher's list shows both students; cancelling frees the seat again.
    mine = bookings.listing(c, tt, org, teacher_id="t1", today=TODAY, now=NOW)
    assert {b.student_name for b in mine} == {s1.name, s2.name}
    bookings.cancel(org, b1.id, s1.name)
    assert next(x for x in bookings.doubt_slots(c, tt, org, s3, TODAY, NOW) if x.date == d).seats_left == 1


def test_meeting_times_are_free_for_every_teacher(world):
    c, tt = world
    org = "bk-meet"
    slots = bookings.meeting_times(c, tt, org, ["t1", "t2"], MON, 3, 1, TODAY, NOW)
    assert slots
    for x in slots:
        on_day = bookings.active(c, tt, x.date)
        assert not [s for s in on_day if s.teacher_id in ("t1", "t2") and bookings._overlaps(s.start, s.end, x.start, x.end)]
    first = slots[0]
    b, msg = bookings.book_meeting(c, tt, org, ["t1", "t2"], first.date, first.start, first.end, "Syllabus review", "",
                                   "u-admin", "Admin", TODAY, NOW)
    assert b is not None and "Meeting booked" in msg
    again = bookings.meeting_times(c, tt, org, ["t1"], MON, 3, 1, TODAY, NOW)
    assert (first.date, first.start) not in {(x.date, x.start) for x in again}
    taken, why = bookings.book_meeting(c, tt, org, ["t1"], first.date, first.start, first.end, "Other", "",
                                       "u-admin", "Admin", TODAY, NOW)
    assert taken is None and "Syllabus review" in why
    # Two-period meetings line up with consecutive periods.
    long = bookings.meeting_times(c, tt, org, ["t2"], MON, 3, 2, TODAY, NOW)
    assert long and all(bookings.to_minutes(x.end) - bookings.to_minutes(x.start) == 120 for x in long)


def test_a_booked_doubt_slot_blocks_meetings(world):
    c, tt = world
    org = "bk-mix"
    h = _hour(org, c, tt, seats=3)
    d = WEEKDAY_OF[h.day]
    st = c.students[0]
    assert bookings.book_doubt(c, tt, org, st, h.id, d, "", "u1", st.name, TODAY, NOW)[0] is not None
    times = bookings.meeting_times(c, tt, org, ["t1"], d, 1, 1, TODAY, NOW)
    assert (d, h.start) not in {(x.date, x.start) for x in times}
    assert "doubt session" in bookings.book_meeting(c, tt, org, ["t1"], d, h.start, h.end, "X", "", "u", "A",
                                                    TODAY, NOW)[1]


def test_a_class_moved_onto_a_booking_is_flagged(world):
    c, tt = world
    org = "bk-clash"
    h = _hour(org, c, tt, seats=3)
    d = WEEKDAY_OF[h.day]
    st = c.students[0]
    b, _ = bookings.book_doubt(c, tt, org, st, h.id, d, "Limits", "u1", st.name, TODAY, NOW)
    assert bookings.listing(c, tt, org, student_id=st.id, today=TODAY, now=NOW)[0].clash is None
    # A one-day change moves one of Dr. A's lectures onto the office hour that day.
    s = next(s for s in tt.sessions if s.teacher_id == "t1" and s.day != h.day)
    period = next(i for i, p in enumerate(c.shifts[0].periods) if p.start == h.start)
    moved = tt.model_copy(update={"overrides": [Override(id="o1", session_id=s.id, date=WEEKDAY_OF[s.day], kind="move",
                                                         to_date=d, start_period=period, venue_id=s.venue_id)]})
    flagged = bookings.listing(c, moved, org, student_id=st.id, today=TODAY, now=NOW)[0]
    assert flagged.id == b.id and flagged.clash and "teaches" in flagged.clash
    assert d not in [x.date for x in bookings.doubt_slots(c, moved, org, c.students[1], TODAY, NOW)]
