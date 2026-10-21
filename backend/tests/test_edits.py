"""Editing: move options, direct moves, repair moves, and the validator after each."""

from app.edits.moves import diff, move_options, repair_move
from app.solver.generate import Pin, generate
from app.validator.check import validate
from tests.conftest import tiny_college


def solved():
    college = tiny_college()
    tt = generate(college, time_limit=10)
    assert tt.sessions and not validate(college, tt.sessions, tt.lunches)
    return college, tt


def test_options_cover_every_slot_with_reasons():
    college, tt = solved()
    s = next(x for x in tt.sessions if x.kind.value == "lecture")
    opts = move_options(college, tt, s.id)
    assert opts and all(o.status in ("free", "repair", "blocked") for o in opts)
    lunch = tt.lunches[0].period
    assert all(o.status == "blocked" for o in opts if o.start_period == lunch)
    assert all(o.reason for o in opts if o.status != "free" or o.venue_id != s.venue_id)


def test_direct_move_changes_only_that_class():
    college, tt = solved()
    s = next(x for x in tt.sessions if x.kind.value == "lecture")
    free = next(o for o in move_options(college, tt, s.id) if o.status == "free")
    new, msg = repair_move(college, tt, s.id, free.day, free.start_period)
    assert new is not None, msg
    assert validate(college, new.sessions, new.lunches) == []
    changes = diff(college, tt.sessions, new.sessions)
    assert len(changes) == 1 and changes[0].session_id == s.id


def test_repair_move_rearranges_clashing_classes_and_stays_valid():
    college, tt = solved()
    for s in tt.sessions:
        for o in move_options(college, tt, s.id):
            if o.status != "repair" or not o.conflicts:
                continue
            new, msg = repair_move(college, tt, s.id, o.day, o.start_period)
            if new is None:
                continue
            assert validate(college, new.sessions, new.lunches) == []
            moved = next(x for x in new.sessions if x.id == s.id)
            assert (moved.day, moved.start_period) == (o.day, o.start_period)
            assert len(diff(college, tt.sessions, new.sessions)) >= 2
            return
    raise AssertionError("expected at least one repairable move in the tiny college")


def test_blocked_slot_is_refused_with_reason():
    college, tt = solved()
    s = next(x for x in tt.sessions if x.kind.value == "lecture")
    blocked = next(o for o in move_options(college, tt, s.id) if o.status == "blocked")
    new, msg = repair_move(college, tt, s.id, blocked.day, blocked.start_period)
    assert new is None and msg


def test_fully_pinned_generation_reproduces_the_timetable():
    college, tt = solved()
    pins = {}
    for s in tt.sessions:
        pins.setdefault(s.allotment_id, []).append(Pin(day=s.day, start=s.start_period, venue_id=s.venue_id))
    again = generate(college, time_limit=10, pins=pins,
                     lunch_pins={(ln.shift_id, ln.year): ln.period for ln in tt.lunches})
    key = lambda ss: sorted((x.allotment_id, x.day, x.start_period, x.venue_id) for x in ss)  # noqa: E731
    assert key(again.sessions) == key(tt.sessions)
