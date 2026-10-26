"""Instant answers: common look-ups answered from the timetable without the model; anything else goes to it."""

import asyncio

from app import quick
from app.tools import ToolContext
from tests.conftest import ADMIN, STUDENT, TEACHER


def ask(backend, member, text, today="2026-10-19", now="09:30"):
    ctx = ToolContext(backend=backend, member=member, today=today, now=now)
    return asyncio.run(quick.answer(ctx, text)), ctx


def test_next_class_today_and_tomorrow_for_a_student(backend):
    out, _ = ask(backend, STUDENT, "What's my next class?")
    assert "Maths now" in out["text"] and "Programming" in out["text"] and "10:00" in out["text"]
    out, _ = ask(backend, STUDENT, "what do i have tomorrow")
    assert out["text"].startswith("Tomorrow you have 1 class") and "11:00 Maths in Room 1, Dr. Anita Sharma" in out["text"]


def test_free_rooms_where_is_and_show_on_screen(backend):
    out, _ = ask(backend, STUDENT, "Which rooms are free right now?")
    assert out["text"].startswith("1 room is free right now") and "Lab (30 seats) all day" in out["text"]
    out, ctx = ask(backend, ADMIN, "Show CSE-1A timetable")
    assert out["text"].startswith("Opened CSE-1A") and ctx.cards[0]["type"] == "navigate"
    assert ctx.cards[0]["path"].startswith("/timetable?view=section&id=s1")


def test_teacher_day_and_staff_only_shortcuts(backend):
    out, _ = ask(backend, TEACHER, "What do I teach today?")
    assert "Maths" in out["text"] and "CSE-1A" in out["text"]
    out, _ = ask(backend, STUDENT, "Show CSE-1A timetable")  # students don't get staff views
    assert out is None


def test_anything_else_goes_to_the_model(backend):
    for q in ["Move maths to Wednesday", "Why is my lab on Monday?", "Where is the canteen?",
              "Dr. Anita Sharma is away tomorrow, plan cover", "What's my next class and can I skip it?"]:
        out, _ = ask(backend, ADMIN if "plan" in q else STUDENT, q)
        assert out is None, q



def test_where_can_i_sit_is_a_free_rooms_answer(backend):
    out, _ = ask(backend, STUDENT, "Where can I sit now?")
    assert out["text"].startswith("1 room is free right now")
