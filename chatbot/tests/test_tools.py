"""Tools: role filtering, schedules, free time, and prepared changes (cards) - never writes."""

import asyncio
import json

import pytest

from app.tools import ToolContext, ToolError, run_tool, tools_for
from tests.conftest import ADMIN, STUDENT, TEACHER


def run(coro):
    return asyncio.run(coro)


def names(role):
    return {t["name"] for t in tools_for(role)}


def test_students_only_get_read_tools():
    s = names("student")
    assert {"my_schedule", "free_time", "free_rooms", "where_is_teacher", "explain_class"} <= s
    assert not s & {"propose_move", "prepare_one_day_change", "one_day_free_times", "timetable_for", "move_options"}
    free = next(t for t in tools_for("student") if t["name"] == "free_time")
    assert "who" not in free["input_schema"]["properties"]  # only their own free time
    assert "propose_move" in names("admin") and "propose_move" not in names("teacher")
    assert all(t["eager_input_streaming"] for t in tools_for("admin"))


def test_forbidden_tool_is_refused_even_if_called(backend):
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="09:30")
    with pytest.raises(ToolError):
        run(run_tool(ctx, "propose_move", {"session_id": "m1", "day": "Wed", "start_time": "09:00"}))


def test_teacher_schedule_is_only_their_own(backend):
    ctx = ToolContext(backend=backend, member=TEACHER, today="2026-10-19", now="09:30")
    out = json.loads(run(run_tool(ctx, "my_schedule", {"from_date": "2026-10-19", "to_date": "2026-10-20"})))
    assert [c["subject"] for c in out["classes"]] == ["MA Maths", "MA Maths"]
    assert {c["teacher"] for c in out["classes"]} == {"Dr. Anita Sharma"}


def test_student_free_time_skips_classes_and_lunch(backend):
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="08:00")
    out = json.loads(run(run_tool(ctx, "free_time", {"from_date": "2026-10-19"})))
    mon = out["days"][0]
    # Classes 09-11 and 14-15, lunch 12-13: free 11-12 and 13-14.
    assert mon["free"] == ["11:00-12:00", "13:00-14:00"] and mon["lunch"] == "lunch 12:00-13:00"


def test_invalid_input_is_reported_not_run(backend):
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="09:00")
    with pytest.raises(ToolError, match="Invalid input"):
        run(run_tool(ctx, "my_schedule", {"from_date": "next tuesday"}))
    with pytest.raises(ToolError, match="at most"):
        run(run_tool(ctx, "my_schedule", {"from_date": "2026-10-01", "to_date": "2026-11-30"}))


def test_propose_move_prepares_a_card_without_applying(backend, fake):
    ctx = ToolContext(backend=backend, member=ADMIN, today="2026-10-19", now="09:00")
    out = json.loads(run(run_tool(ctx, "propose_move", {"session_id": "m1", "day": "Wed", "start_time": "09:00"})))
    assert out["prepared"] and ctx.cards[0]["type"] == "proposal" and ctx.cards[0]["proposal"]["id"] == "p-1"
    assert not any(path.endswith("/apply") for _, path, _ in fake.calls)  # the user applies, not the assistant
    with pytest.raises(ToolError, match="lunch"):
        run(run_tool(ctx, "propose_move", {"session_id": "m1", "day": "Mon", "start_time": "12:00"}))


def test_one_day_change_checks_day_and_owner(backend):
    t = ToolContext(backend=backend, member=TEACHER, today="2026-10-19", now="09:00")
    with pytest.raises(ToolError, match="different day"):
        run(run_tool(t, "prepare_one_day_change", {"session_id": "m1", "date": "2026-10-20", "kind": "cancel"}))
    with pytest.raises(ToolError, match="own lectures"):
        run(run_tool(t, "prepare_one_day_change", {"session_id": "p1", "date": "2026-10-19", "kind": "cancel"}))
    out = json.loads(run(run_tool(t, "prepare_one_day_change", {
        "session_id": "m1", "date": "2026-10-19", "kind": "move", "start_time": "11:00", "reason": "Exam duty"})))
    card = t.cards[0]["action"]
    assert out["prepared"] and card["start_period"] == 2 and card["to_date"] == "2026-10-19"
    assert "Exam duty" in card["summary"]


def test_names_are_resolved_loosely(backend):
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="09:30")
    out = json.loads(run(run_tool(ctx, "where_is_teacher", {"teacher": "anita"})))
    assert out["status"] == "teaching" and out["room"] == "Room 1"
    with pytest.raises(ToolError, match="Couldn't find"):
        run(run_tool(ctx, "where_is_teacher", {"teacher": "Nobody"}))


def test_free_rooms_say_whose_room_it_is(backend):
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="10:00")
    out = json.loads(asyncio.run(run_tool(ctx, "free_rooms", {})))
    assert out["free"][0]["belongs_to"] == "CSE"
