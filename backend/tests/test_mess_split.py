"""Mess split (Try rule "spread_lunch"): lunches spread evenly over the mess window, by section strength."""

from collections import Counter

from app.main import _rule_errors
from app.models.domain import Allotment, Kind, Rule, Section, Subject, Teacher
from app.solver.generate import generate
from app.solver.quality import score
from app.validator.check import validate
from tests.conftest import tiny_college

SPREAD = Rule(id="mess", name="Spread lunch", kind="spread_lunch", mode="try", weight=8)


def _four_sections(rules=()):
    """Four equal sections in one shift whose mess window holds two periods (12:00 and 13:00)."""
    secs = [Section(id=f"s{i}", name=f"CSE-1{'ABCD'[i - 1]}", department_id="cse", year=1, strength=40,
                    shift_id="day") for i in range(1, 5)]
    teachers = [Teacher(id=f"t{i}", name=f"Dr. T{i}", department_id="cse", shift_ids=["day"], max_per_day=5)
                for i in range(1, 5)]
    subjects = [Subject(id="maths", code="MA", name="Maths", department_id="cse", year=1, lectures_per_week=3)]
    allots = [Allotment(id=f"a{i}", subject_id="maths", teacher_id=f"t{i}", kind=Kind.lecture, section_ids=[f"s{i}"])
              for i in range(1, 5)]
    c = tiny_college(sections=secs, teachers=teachers, subjects=subjects, allotments=allots, rules=list(rules))
    rooms = [v.model_copy(update={"id": f"r{i}", "name": f"Room {i}"}) for i, v in enumerate(c.venues * 4, 1)
             if v.type == "lecture"]
    return c.model_copy(update={"venues": rooms})


def test_lunches_split_evenly_when_the_rule_is_on():
    c = _four_sections([SPREAD])
    assert c.shifts[0].lunch_candidates() == [3, 4]
    tt = generate(c, time_limit=10)
    assert tt.status in ("optimal", "feasible") and not validate(c, tt.sessions, tt.lunches)
    for day in c.days:
        per_period = Counter(ln.period for ln in tt.lunches if ln.day == day)
        assert sorted(per_period.values()) == [2, 2], (day, per_period)
    item = next(i for i in score(c, tt.sessions, tt.lunches).items if i.key == "mess_split")
    assert item.penalty == 0


def test_rule_is_only_scored_when_on_and_is_always_a_try_rule():
    c = _four_sections()
    tt = generate(c, time_limit=10)
    assert all(i.key != "mess_split" for i in score(c, tt.sessions, tt.lunches).items)
    assert _rule_errors(c, [SPREAD]) == []
    must = SPREAD.model_copy(update={"mode": "must"})
    assert any("always a Try rule" in e for e in _rule_errors(c, [must]))
