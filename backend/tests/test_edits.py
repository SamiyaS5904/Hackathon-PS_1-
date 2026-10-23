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
    assert all(o.reason for o in opts if o.status != "free" or o.venue_id != s.venue_id)
    # Lunch is flexible: a "free" slot may be a mess-window period, but the move still leaves every
    # section a free lunch period that day (the validator would say otherwise).
    for o in (o for o in opts if o.status == "free"):
        new, msg = repair_move(college, tt, s.id, o.day, o.start_period)
        assert new is not None, msg
        assert validate(college, new.sessions, new.lunches) == []


def test_lunch_is_per_section_per_day_and_can_differ_by_day():
    college, tt = solved()
    sec = college.sections[0]
    mine = {ln.day: ln for ln in tt.lunches if ln.section_id == sec.id}
    assert set(mine) == set(college.days)  # one lunch every working day
    window = college.shift(sec.shift_id).lunch
    assert all(window.window_start <= ln.start and ln.end <= window.window_end for ln in mine.values())


def test_move_refused_when_it_would_take_the_last_lunch_period():
    from app import lunch
    from app.edits.moves import check_slot

    college, tt = solved()
    sec = college.sections[0]
    day = college.days[0]
    shift = college.shift(sec.shift_id)
    free = lunch.free_periods(college, tt.sessions, sec, day)
    s = next(x for x in tt.sessions if sec.id in x.section_ids and x.kind.value == "lecture" and x.length == 1)
    others = [x for x in tt.sessions if x.id != s.id]
    if len(free) == 1:  # placing a class on the only free lunch period must be refused
        opt = check_slot(college, s, day, free[0], others, tt.lunches)
        assert opt.status == "blocked" and "lunch" in opt.reason
    # The helper itself: an extra class over every free window period leaves no lunch.
    if free:
        lo = shift.periods[min(free)].start_min
        hi = shift.periods[max(free)].end_min
        assert not lunch.keeps_lunch(college, tt.sessions, sec, day, (lo, hi))


def test_direct_move_changes_only_that_class():
    college, tt = solved()
    s, free = next((x, o) for x in tt.sessions if x.kind.value == "lecture"
                   for o in move_options(college, tt, x.id) if o.status == "free")
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


def test_every_repaired_move_passes_the_apply_check():
    """Apply re-runs the validator on the proposal exactly as stored, lunches included."""
    college, tt = solved()
    tried = 0
    for s in (x for x in tt.sessions if x.kind.value == "lecture"):
        for o in (o for o in move_options(college, tt, s.id) if o.status == "repair"):
            new, msg = repair_move(college, tt, s.id, o.day, o.start_period)
            if new is not None:
                assert validate(college, new.sessions, new.lunches) == [], msg
                tried += 1
            if tried >= 6:
                return


def test_a_move_keeps_other_sections_lunches():
    college, tt = solved()
    s, o = next((x, o) for x in tt.sessions if x.kind.value == "lecture"
                for o in move_options(college, tt, x.id) if o.status in ("free", "repair"))
    new, msg = repair_move(college, tt, s.id, o.day, o.start_period)
    assert new is not None, msg
    untouched_days = set(college.days) - {o.day, s.day}
    before = {(ln.section_id, ln.day): ln.period for ln in tt.lunches if ln.day in untouched_days}
    after = {(ln.section_id, ln.day): ln.period for ln in new.lunches if ln.day in untouched_days}
    assert before == after
