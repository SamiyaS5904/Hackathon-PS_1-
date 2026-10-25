"""One-day changes: cancel / move on a date, the weekly template stays untouched."""

from app.edits.oneday import active, add_override, day_options, occurrences, remove_override, week
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college

MONDAY = "2026-10-19"  # tiny college works Mon-Wed


DATES = {"Mon": "2026-10-19", "Tue": "2026-10-20", "Wed": "2026-10-21"}


def movable(college, tt):
    """A lecture with a free slot on its own day (the tiny college is packed, so search every day)."""
    return next((x, DATES[x.day], o) for x in tt.sessions if x.kind.value == "lecture"
                for o in day_options(college, tt, x.id, DATES[x.day], DATES[x.day]) if o.status == "free")


def solved():
    college = tiny_college()
    tt = generate(college, time_limit=10)
    return college, tt


def test_week_lists_working_days_with_dates():
    college, _ = solved()
    days = week(college, "2026-10-21")  # a Wednesday
    assert [d.date for d in days] == ["2026-10-19", "2026-10-20", "2026-10-21"]
    assert days[0].label == "Mon 19 Oct"


def test_cancel_only_affects_that_date():
    college, tt = solved()
    s = next(x for x in tt.sessions if x.day == "Mon")
    new, msg, _ = add_override(college, tt, s.id, MONDAY, "cancel", None, None, "Teacher at a conference", "Admin")
    assert new is not None, msg
    assert any(o.status == "cancelled" and o.session.id == s.id for o in occurrences(college, new, MONDAY))
    assert s.id in {x.id for x in active(college, new, "2026-10-26")}  # next Monday unchanged
    assert new.sessions == tt.sessions  # weekly template untouched


def test_move_for_one_day_uses_only_free_slots_and_stays_clash_free():
    college, tt = solved()
    s, day, free = movable(college, tt)
    opts = day_options(college, tt, s.id, day, day)
    assert all(o.status in ("free", "blocked") for o in opts)
    new, msg, _ = add_override(college, tt, s.id, day, "move", day, free.start_period, "", "Admin")
    assert new is not None, msg
    from app.edits.oneday import _day
    assert validate(college, *_day(college, new, day), check_counts=False) == []
    moved = next(x for x in active(college, new, day) if x.id == s.id)
    assert moved.start_period == free.start_period

    blocked = next((o for o in opts if o.status == "blocked"), None)
    if blocked:
        bad, err, _ = add_override(college, tt, s.id, DATES[s.day], "move", DATES[s.day], blocked.start_period, "",
                                   "Admin")
        assert bad is None and err


def test_wrong_date_and_double_change_are_refused():
    college, tt = solved()
    s = next(x for x in tt.sessions if x.day == "Mon")
    assert add_override(college, tt, s.id, "2026-10-20", "cancel", None, None, "", "Admin")[0] is None  # a Tuesday
    once, _, _ = add_override(college, tt, s.id, MONDAY, "cancel", None, None, "", "Admin")
    assert add_override(college, once, s.id, MONDAY, "cancel", None, None, "", "Admin")[0] is None


def test_restore_removes_the_change():
    college, tt = solved()
    s = next(x for x in tt.sessions if x.day == "Mon")
    new, _, _ = add_override(college, tt, s.id, MONDAY, "cancel", None, None, "", "Admin")
    restored, msg = remove_override(college, new, new.overrides[0].id)
    assert restored is not None and restored.overrides == []


def test_occurrence_ids_are_stable_when_a_class_moves():
    """Future attendance hooks onto occurrence ids: a moved class keeps the id of its original date."""
    college, tt = solved()
    s, day, free = movable(college, tt)
    before = next(o for o in occurrences(college, tt, day) if o.session.id == s.id)
    assert before.occurrence_id == f"{s.id}@{day}"
    new, msg, _ = add_override(college, tt, s.id, day, "move", day, free.start_period, "", "Admin")
    assert new is not None, msg
    ids = {o.status: o.occurrence_id for o in occurrences(college, new, day) if o.session.id == s.id}
    assert ids["moved_in"] == ids["moved_out"] == before.occurrence_id


def test_makeup_finder_books_a_cancelled_class_and_stays_clash_free():
    from app.edits.oneday import _day, makeup_options

    college, tt = solved()

    def cancel_and_find(x):
        c, _, _ = add_override(college, tt, x.id, MONDAY, "cancel", None, None, "Teacher unwell", "Admin")
        return c, makeup_options(college, c, x.id, MONDAY, today=MONDAY, days=14)

    s, cancelled, opts = next((x, *cancel_and_find(x)) for x in tt.sessions
                              if x.day == "Mon" and x.kind.value == "lecture" and cancel_and_find(x)[1])
    assert all(o.date >= MONDAY for o in opts)
    assert opts == sorted(opts, key=lambda o: (o.date, o.start))  # soonest first
    pick = opts[0]
    booked, msg, _ = add_override(college, cancelled, s.id, MONDAY, "move", pick.date, pick.start_period, "Makeup",
                                  "Admin")
    assert booked is not None, msg
    mine = [o for o in booked.overrides if o.session_id == s.id and o.date == MONDAY]
    assert len(mine) == 1 and mine[0].kind == "move"  # the makeup replaced the cancellation
    assert validate(college, *_day(college, booked, pick.date), check_counts=False) == []
    # Nothing in the past is offered.
    later = makeup_options(college, cancelled, s.id, MONDAY, today="2026-10-21", days=7)
    assert all(o.date >= "2026-10-21" for o in later)


def test_moving_to_another_day_respects_the_classs_own_weekly_slot_there():
    """Next Monday the same class happens at its usual time: a one-day move must not land on top of it."""
    college, tt = solved()
    s = next(x for x in tt.sessions if x.day == "Mon" and x.kind.value == "lecture")
    opts = day_options(college, tt, s.id, MONDAY, "2026-10-26")
    assert all(o.status == "blocked" for o in opts if o.start_period == s.start_period)
