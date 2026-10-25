"""Mid-semester regenerate with minimal change: only what must move moves; ids and one-day changes carry over."""

from app.edits import regenerate
from app.models.domain import Override, Session, TimeBlock
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college

MON = "2026-11-02"
WEEKDAY_DATE = {"Mon": "2026-11-02", "Tue": "2026-11-03", "Wed": "2026-11-04"}


def test_a_new_block_time_moves_only_the_class_that_must_move():
    c = tiny_college()
    old = generate(c, time_limit=10)
    target = next(s for s in old.sessions if s.teacher_id == "t1")
    c2 = c.model_copy(deep=True)
    c2.teachers[0].blocked = [TimeBlock(day=target.day, start=target.start, end=target.end)]  # Dr. A can't teach then

    new = generate(c2, time_limit=10, keep=regenerate.keep_map(old))
    tt, summary = regenerate.finish(c2, old, new, actor="Admin")
    assert validate(c2, tt.sessions, tt.lunches) == []
    assert 1 <= summary.moved <= 3 and summary.kept >= len(old.sessions) - 3
    assert summary.added == summary.removed == 0
    moved_ids = {ch.session_id for ch in summary.changes}
    assert target.id in moved_ids  # the blocked class moved, and kept its id
    old_by_id = {s.id: s for s in old.sessions}
    for s in tt.sessions:  # every class that didn't move kept its id, day and time
        if s.id not in moved_ids:
            assert (old_by_id[s.id].day, old_by_id[s.id].start_period) == (s.day, s.start_period)
    assert "stayed where they were" in summary.sentence()


def test_one_day_changes_carry_over_or_are_dropped_with_a_reason():
    c = tiny_college()
    old = generate(c, time_limit=10)
    target = next(s for s in old.sessions if s.teacher_id == "t1")
    other = next(s for s in old.sessions if s.teacher_id == "t2" and s.day != target.day)
    old = old.model_copy(update={"overrides": [
        Override(id="o1", session_id=target.id, date=WEEKDAY_DATE[target.day], kind="cancel", reason="Exam duty"),
        Override(id="o2", session_id=other.id, date=WEEKDAY_DATE[other.day], kind="cancel", reason="Seminar"),
    ]})
    c2 = c.model_copy(deep=True)
    c2.teachers[0].blocked = [TimeBlock(day=target.day, start=target.start, end=target.end)]
    new = generate(c2, time_limit=10, keep=regenerate.keep_map(old))
    tt, summary = regenerate.finish(c2, old, new, actor="Admin")
    assert summary.one_day_kept == 1 and len(summary.one_day_dropped) == 1
    assert "the class moved" in summary.one_day_dropped[0]
    assert [(o.session_id, o.reason) for o in tt.overrides] == [(other.id, "Seminar")]


def test_new_classes_never_reuse_a_removed_class_id():
    s = dict(subject_id="m", teacher_id="t1", venue_id="r1", kind="lecture", section_ids=["s1"], shift_id="day",
             length=1, start="09:00", end="10:00")
    old = [Session(id="s1", allotment_id="a1", day="Mon", start_period=0, **s),
           Session(id="s2", allotment_id="gone", day="Tue", start_period=0, **s)]
    new = [Session(id="x", allotment_id="a1", day="Wed", start_period=1, **s),
           Session(id="y", allotment_id="fresh", day="Mon", start_period=2, **s)]
    out = {n.allotment_id: n.id for n in regenerate.stable_ids(old, new)}
    assert out == {"a1": "s1", "fresh": "s3"}  # moved class keeps its id; the new one doesn't take s2
