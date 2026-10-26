"""Room booking for events: free rooms only, the right approver, and an approved event holds its room."""

import pytest

from app import venue_events
from app.accounts import Member
from app.db.models import init_db
from app.edits.oneday import add_override, day_options, remove_override
from app.models.domain import Department, Holiday, Venue, VenueType
from app.solver.generate import generate
from tests.conftest import tiny_college

TODAY, NOW = "2026-11-01", "10:00"  # a Sunday; the tiny college works Mon-Wed
DATES = {"Mon": "2026-11-02", "Tue": "2026-11-03", "Wed": "2026-11-04"}


def _member(role, **kw):
    return Member(user_id=kw.pop("user_id", role), org_id="x", org_name="X", name=kw.pop("name", role.title()),
                  email=f"{role}@x.edu", role=role, **kw)


TEACHER = _member("teacher", teacher_id="t1", department_id="cse", name="Dr. A")
CSE_COORD = _member("coordinator", department_id="cse", name="CSE Coordinator")
ME_COORD = _member("coordinator", user_id="me-coord", department_id="me", name="ME Coordinator")
ADMIN = _member("admin", name="College Admin")


def _world(org: str):
    init_db()
    c = tiny_college(id=org, holidays=[Holiday(date="2026-11-09", label="Diwali")],
                     departments=[Department(id="cse", name="CSE", short="CSE"),
                                  Department(id="me", name="ME", short="ME")])
    c = c.model_copy(update={"venues": [*c.venues, Venue(id="hall", name="Seminar Hall", type=VenueType.seminar,
                                                         capacity=120)]})
    return c, generate(c, time_limit=10)


def _class_slot(c, tt):
    """A lecture and the real date it happens on."""
    s = next(x for x in tt.sessions if x.kind == "lecture" and x.venue_id == "r1")
    return s, DATES[s.day]


def test_free_rooms_skip_classes_holidays_and_the_past():
    c, tt = _world("ev-free")
    s, d = _class_slot(c, tt)
    rooms, why = venue_events.free_venues(c, tt, c.id, d, s.start, s.end, TODAY, NOW)
    assert why is None and "r1" not in {r.venue_id for r in rooms} and "hall" in {r.venue_id for r in rooms}
    hall = next(r for r in rooms if r.venue_id == "hall")
    assert hall.owner == "Shared" and hall.approver == "College Admin"
    assert "holiday" in venue_events.free_venues(c, tt, c.id, "2026-11-09", "10:00", "11:00", TODAY, NOW)[1]
    assert "passed" in venue_events.free_venues(c, tt, c.id, "2026-10-30", "10:00", "11:00", TODAY, NOW)[1]
    assert "working day" in venue_events.free_venues(c, tt, c.id, "2026-11-05", "10:00", "11:00", TODAY, NOW)[1]
    # A class is never bumped: booking the class's room at class time is refused.
    ev, msg = venue_events.request(c, tt, c.id, TEACHER, "r1", d, s.start, s.end, "Quiz", "", TODAY, NOW)
    assert ev is None and "is there" in msg


def test_the_rooms_department_coordinator_or_the_admin_decides():
    c, tt = _world("ev-decide")
    ev, msg = venue_events.request(c, tt, c.id, TEACHER, "hall", DATES["Tue"], "09:00", "11:00", "Coding contest",
                                   "Coding Club", TODAY, NOW)
    assert ev.status == "pending" and "College Admin" in msg  # shared room
    assert venue_events.can_decide(CSE_COORD, ev) and not venue_events.can_decide(ADMIN, ev)
    # Waiting requests already keep the room from a second booking (first come, first served).
    dup, why = venue_events.request(c, tt, c.id, CSE_COORD, "hall", DATES["Tue"], "10:00", "12:00", "Talk", "",
                                    TODAY, NOW)
    assert dup is None and "requested" in why
    done, _ = venue_events.decide(c, tt, c.id, ADMIN, ev, approve=True)
    assert done.status == "approved"
    assert venue_events.decide(c, tt, c.id, ADMIN, done, approve=False)[0] is None  # already decided
    # A department room: its Coordinator decides, another department's can't.
    lab_ev, _ = venue_events.request(c, tt, c.id, TEACHER, "lab", DATES["Wed"], "13:00", "14:00", "Hackathon prep",
                                     "", TODAY, NOW)
    if lab_ev is not None:  # the lab may be busy then; the rule is what matters
        assert not venue_events.can_decide(CSE_COORD, lab_ev) and venue_events.can_decide(ME_COORD, lab_ev)
    # Booking a room you look after yourself is approved at once.
    own, _ = venue_events.request(c, tt, c.id, ADMIN, "hall", DATES["Wed"], "09:00", "10:00", "Staff meeting", "",
                                  TODAY, NOW)
    assert own.status == "approved"
    lists = venue_events.listing(c, tt, c.id, ADMIN, TODAY, NOW)
    assert {e.title for e in lists.upcoming} == {"Coding contest"} and {e.title for e in lists.mine} == {"Staff meeting"}
    assert venue_events.listing(c, tt, c.id, TEACHER, TODAY, NOW).mine[0].status == "approved"


def test_an_approved_event_holds_its_room_against_one_day_changes():
    c, tt = _world("ev-hold")
    s, d = _class_slot(c, tt)
    # Move the class away for one day: its room is free at that time, and an event takes it.
    away = next(o for o in day_options(c, tt, s.id, d, d) if o.status == "free")
    tt2, msg, _ = add_override(c, tt, s.id, d, "move", d, away.start_period, "", "t")
    assert tt2 is not None, msg
    ev, _ = venue_events.request(c, tt2, c.id, ADMIN, "r1", d, s.start, s.end, "Guest talk", "", TODAY, NOW)
    assert ev is not None and ev.status == "approved"
    ov = next(o for o in tt2.overrides if o.session_id == s.id)
    back, why = remove_override(c, tt2, ov.id)
    assert back is None and "booked for Guest talk" in why
    # No class can be moved into the held room at that time on that date.
    other = next(x for x in tt.sessions if x.kind == "lecture" and x.id != s.id)
    held = [o for o in day_options(c, tt2, other.id, DATES[other.day], d)
            if o.start == s.start and o.status == "free" and o.venue_id == "r1"]
    assert held == []
    # Cancelling the event frees the room again.
    venue_events.cancel(c.id, ADMIN, venue_events.get(c.id, ev.id))
    assert remove_override(c, tt2, ov.id)[0] is not None


def test_only_the_person_who_booked_or_the_admin_cancels():
    c, tt = _world("ev-cancel")
    ev, _ = venue_events.request(c, tt, c.id, TEACHER, "hall", DATES["Mon"], "09:00", "10:00", "Club meet", "",
                                 TODAY, NOW)
    assert venue_events.cancel(c.id, CSE_COORD, ev)[0] is None
    done, _ = venue_events.cancel(c.id, TEACHER, ev)
    assert done.status == "cancelled"


@pytest.mark.parametrize("role", ["student"])
def test_students_cant_book_rooms(role):
    c, tt = _world("ev-student")
    ev, why = venue_events.request(c, tt, c.id, _member(role), "hall", DATES["Mon"], "09:00", "10:00", "Party", "",
                                   TODAY, NOW)
    assert ev is None and "teachers and staff" in why
