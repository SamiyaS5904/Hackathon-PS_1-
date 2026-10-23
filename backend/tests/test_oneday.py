"""One-day changes: cancel / move on a date, the weekly template stays untouched."""

from app.edits.oneday import active, add_override, day_options, occurrences, remove_override, week
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college

MONDAY = "2026-10-19"  # tiny college works Mon-Wed


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
    s = next(x for x in tt.sessions if x.day == "Mon" and x.kind.value == "lecture")
    opts = day_options(college, tt, s.id, MONDAY, MONDAY)
    assert all(o.status in ("free", "blocked") for o in opts)
    free = next(o for o in opts if o.status == "free")
    new, msg, _ = add_override(college, tt, s.id, MONDAY, "move", MONDAY, free.start_period, "", "Admin")
    assert new is not None, msg
    day = active(college, new, MONDAY)
    assert validate(college, day, new.lunches, check_counts=False) == []
    moved = next(x for x in day if x.id == s.id)
    assert moved.start_period == free.start_period

    blocked = next((o for o in opts if o.status == "blocked"), None)
    if blocked:
        bad, err, _ = add_override(college, tt, s.id, MONDAY, "move", MONDAY, blocked.start_period, "", "Admin")
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
    s = next(x for x in tt.sessions if x.day == "Mon" and x.kind.value == "lecture")
    before = next(o for o in occurrences(college, tt, MONDAY) if o.session.id == s.id)
    assert before.occurrence_id == f"{s.id}@{MONDAY}"
    free = next(o for o in day_options(college, tt, s.id, MONDAY, MONDAY) if o.status == "free")
    new, msg, _ = add_override(college, tt, s.id, MONDAY, "move", MONDAY, free.start_period, "", "Admin")
    assert new is not None, msg
    ids = {o.status: o.occurrence_id for o in occurrences(college, new, MONDAY) if o.session.id == s.id}
    assert ids["moved_in"] == ids["moved_out"] == before.occurrence_id
