"""Reschedule finder: times when the teacher, every student and a room are free, marked when free every week."""

from app.edits.moves import move_options
from app.edits.oneday import add_override, weekday
from app.reschedule import reschedule_options
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college

TODAY = "2026-11-02"  # a Monday; the tiny college works Mon-Wed


def test_options_are_free_for_everyone_and_each_one_can_be_applied():
    c = tiny_college()
    tt = generate(c, time_limit=10)
    s = next(x for x in tt.sessions if x.kind == "lecture")
    d = _date_of(s.day)
    out = reschedule_options(c, tt, s.id, d, TODAY, "08:00")
    assert out.options and not out.note
    weekly = {(o.day, o.start_period) for o in move_options(c, tt, s.id) if o.status == "free"}
    for o in out.options:
        assert weekday(c, o.date) == o.day and o.every_week == ((o.day, o.start_period) in weekly)
        assert not (o.date == d and o.start_period == s.start_period)
    # Every offered time really works as a one-day move: the validator agrees.
    for o in out.options[:5]:
        new, msg, _ = add_override(c, tt, s.id, d, "move", o.date, o.start_period, "", "t")
        assert new is not None, msg
        assert not validate(c, new.sessions, new.lunches)


def test_times_already_past_today_are_skipped():
    c = tiny_college()
    tt = generate(c, time_limit=10)
    s = next(x for x in tt.sessions if x.kind == "lecture")
    late = reschedule_options(c, tt, s.id, _date_of(s.day), TODAY, "13:30")
    assert all(not (o.date == TODAY and o.start <= "13:30") for o in late.options)


def _date_of(day: str) -> str:
    return {"Mon": "2026-11-02", "Tue": "2026-11-03", "Wed": "2026-11-04"}[day]
