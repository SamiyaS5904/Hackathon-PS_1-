import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backend import Backend  # noqa: E402

PERIODS = [{"start": a, "end": b} for a, b in [("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
                                                ("12:00", "13:00"), ("13:00", "14:00"), ("14:00", "15:00")]]
COLLEGE = {
    "id": "c", "name": "Sunrise College", "days": ["Mon", "Tue", "Wed", "Thu", "Fri"], "lab_periods": 2,
    "shifts": [{"id": "day", "name": "Day", "periods": PERIODS, "lunch": {"window_start": "12:00", "window_end": "14:00"}}],
    "departments": [{"id": "cse", "name": "CSE", "short": "CSE"}],
    "venues": [{"id": "r1", "name": "Room 1", "type": "lecture", "capacity": 60, "tags": [], "department_id": "cse"},
               {"id": "lab", "name": "Lab", "type": "lab", "capacity": 30, "tags": ["computers"], "department_id": "cse"}],
    "sections": [{"id": "s1", "name": "CSE-1A", "department_id": "cse", "year": 1, "strength": 60, "shift_id": "day",
                  "batches": [{"id": "b1", "name": "B1", "strength": 30}, {"id": "b2", "name": "B2", "strength": 30}]}],
    "teachers": [{"id": "t1", "name": "Dr. Anita Sharma", "department_id": "cse", "shift_ids": ["day"], "max_per_day": 5},
                 {"id": "t2", "name": "Prof. Ravi Kumar", "department_id": "cse", "shift_ids": ["day"], "max_per_day": 5}],
    "subjects": [{"id": "ma", "code": "MA", "name": "Maths", "department_id": "cse", "year": 1, "lectures_per_week": 3,
                  "labs_per_week": 0, "lab_tag": None},
                 {"id": "cs", "code": "CS", "name": "Programming", "department_id": "cse", "year": 1,
                  "lectures_per_week": 2, "labs_per_week": 1, "lab_tag": "computers"}],
    "students": [], "teacher_subjects": [], "elective_slots": [], "holidays": [], "rules": [],
    "department_status": {}, "revision": 1,
}


def session(sid, subject, teacher, venue, day, start, end, period, kind="lecture", batch=None):
    return {"id": sid, "allotment_id": "a", "subject_id": subject, "teacher_id": teacher, "venue_id": venue,
            "kind": kind, "section_ids": ["s1"], "batch_id": batch, "day": day, "shift_id": "day",
            "start_period": period, "length": 2 if kind == "lab" else 1, "start": start, "end": end,
            "elective_slot_id": None, "group_id": None}


SESSIONS = [
    session("m1", "ma", "t1", "r1", "Mon", "09:00", "10:00", 0),
    session("p1", "cs", "t2", "r1", "Mon", "10:00", "11:00", 1),
    session("l1", "cs", "t2", "lab", "Mon", "14:00", "15:00", 5, kind="lecture"),
    session("m2", "ma", "t1", "r1", "Tue", "11:00", "12:00", 2),
]
TIMETABLE = {"timetable": {"sessions": SESSIONS, "lunches": [
    {"shift_id": "day", "section_id": "s1", "day": d, "period": 3, "start": "12:00", "end": "13:00"}
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]], "overrides": []},
             "quality": {"score": 88, "items": []}, "violations": [], "stale": False}


def week(start):
    days = [{"date": d, "day": n, "label": n, "working": True, "holiday": None}
            for d, n in [("2026-10-19", "Mon"), ("2026-10-20", "Tue"), ("2026-10-21", "Wed"),
                         ("2026-10-22", "Thu"), ("2026-10-23", "Fri")]]
    date_of = {d["day"]: d["date"] for d in days}
    occ = [{"session": s, "date": date_of[s["day"]], "status": "normal", "override_id": None, "note": ""} for s in SESSIONS]
    return {"days": days, "occurrences": occ}


class FakeBackend:
    """Serves canned responses and records every request (method, path, json)."""

    def __init__(self):
        self.calls = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body))
        if path.endswith("/college"):
            return httpx.Response(200, json=COLLEGE)
        if path.endswith("/timetable/week"):
            return httpx.Response(200, json=week(request.url.params["start"]))
        if path.endswith("/timetable"):
            return httpx.Response(200, json=TIMETABLE)
        if path.endswith("/options"):
            return httpx.Response(200, json=[
                {"day": "Wed", "start_period": 0, "start": "09:00", "end": "10:00", "status": "free", "reason": "",
                 "venue_id": "r1", "conflicts": []},
                {"day": "Mon", "start_period": 3, "start": "12:00", "end": "13:00", "status": "blocked",
                 "reason": "That's the lunch period for these students.", "venue_id": None, "conflicts": []}])
        if path.endswith("/proposals"):
            return httpx.Response(201, json={"id": "p-1", "message": "Moved. Nothing else had to change.",
                                             "changes": [{"session_id": "m1", "subject": "Maths", "sections": "CSE-1A",
                                                          "before": "Mon 09:00-10:00", "after": "Wed 09:00-10:00"}],
                                             "quality_before": 88, "quality_after": 88})
        if path.endswith("/day-options"):
            return httpx.Response(200, json=[
                {"day": "Mon", "start_period": 2, "start": "11:00", "end": "12:00", "status": "free", "reason": "",
                 "venue_id": "r1", "conflicts": []}])
        if path.endswith("/free-rooms"):
            return httpx.Response(200, json=[{"venue_id": "lab", "name": "Lab", "type": "lab", "capacity": 30,
                                              "department": "cse", "free_until": None}])
        if path.endswith("/makeup"):
            return httpx.Response(200, json=[{"date": "2026-10-21", "label": "Wed 21 Oct", "start_period": 0,
                                              "start": "09:00", "end": "10:00", "venue_id": "r1", "venue": "Room 1"}])
        if path.endswith("/attendance/me"):
            return httpx.Response(200, json={
                "min_percent": 75, "held": 4, "attended": 2, "percent": 50.0, "status": "low",
                "advice": "Below 75%: attend the next 4 classes in a row to get back.",
                "subjects": [{"subject_id": "ma", "code": "MA", "name": "Maths", "held": 4, "attended": 2,
                              "percent": 50.0, "status": "low", "advice": "Below 75%."}],
                "recent": [{"date": "2026-10-19", "subject": "Maths", "present": False}]})
        if path.endswith("/attendance/my-classes"):
            return httpx.Response(200, json=[
                {"session_id": "m1", "date": "2026-10-19", "label": "Mon 19 Oct", "subject": "Maths",
                 "sections": "CSE-1A", "start": "09:00", "end": "10:00", "venue": "Room 1", "students": 40,
                 "marked": False, "absent": 0, "can_edit": True}])
        if "/attendance/sections/" in path:
            return httpx.Response(200, json={"section": "CSE-1A", "min_percent": 75, "students": [
                {"student_id": "st1", "roll_no": "01", "name": "Aarav", "held": 4, "attended": 2, "percent": 50.0,
                 "low": True},
                {"student_id": "st2", "roll_no": "02", "name": "Diya", "held": 4, "attended": 4, "percent": 100.0,
                 "low": False}]})
        if path == "/api/platform/overview":
            item = {"id": "new-college", "name": "New College", "is_demo": False, "created_at": 0, "plan": "trial",
                    "status": "active", "note": "", "stage": "Setting up", "departments": 0, "departments_ready": 0,
                    "sections": 0, "teachers": 0, "students": 0, "accounts": 1, "classes": 0, "published_at": None,
                    "attendance_marked": 0, "bookings": 0, "last_activity": 0,
                    "flags": ["Signed up 5 days ago but hasn't started the setup."], "needs_attention": True}
            demo = item | {"id": "demo", "name": "Demo Institute", "is_demo": True, "stage": "Live", "students": 720,
                           "flags": [], "needs_attention": False}
            return httpx.Response(200, json={"colleges": 2, "live": 1, "needs_attention": 1, "students": 720,
                                             "teachers": 40, "sections": 12, "classes": 238, "accounts": 800,
                                             "attendance_marked": 3, "bookings": 1, "plans": {"trial": 2},
                                             "items": [item, demo]})
        if path.endswith("/bookings/doubt-slots"):
            return httpx.Response(200, json=[{"date": "2026-10-20", "label": "Tue 20 Oct", "start": "11:00", "end": "12:00",
                                              "teacher_id": "t1", "teacher_name": "Dr. Anita Sharma",
                                              "office_hour_id": "oh1", "place": "Staff room", "seats_left": 2}])
        if path.endswith("/bookings/teachers"):
            return httpx.Response(200, json=[])
        if path.endswith("/bookings/meeting-times"):
            return httpx.Response(200, json=[{"date": "2026-10-20", "label": "Tue 20 Oct", "start": "13:00", "end": "14:00",
                                              "teacher_id": None, "teacher_name": "", "office_hour_id": None,
                                              "place": "", "seats_left": None}])
        if path.endswith("/bookings"):
            return httpx.Response(200, json=[{"id": "b1", "kind": "doubt", "date": "2026-10-20", "label": "Tue 20 Oct",
                                              "start": "11:00", "end": "12:00", "teacher_ids": ["t1"],
                                              "teacher_names": ["Dr. Anita Sharma"], "title": "Limits", "place": "",
                                              "student_name": "Aarav", "section": "CSE-1A", "created_by": "u",
                                              "created_by_name": "Aarav", "status": "booked", "cancelled_by": "",
                                              "clash": None, "past": False}])
        if "/teachers/" in path:
            return httpx.Response(200, json={"teacher": "Dr. Anita Sharma", "date": "Mon 19 Oct", "time": "09:30",
                                             "status": "teaching", "subject": "Maths", "room": "Room 1",
                                             "sections": "CSE-1A", "until": "10:00", "next_class": None})
        return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
def fake():
    return FakeBackend()


@pytest.fixture
def backend(fake):
    return Backend("tok", "c", transport=httpx.MockTransport(fake.handler))


STUDENT = {"role": "student", "name": "Aarav", "section_id": "s1", "batch_id": "b1", "teacher_id": None}
TEACHER = {"role": "teacher", "name": "Dr. Anita Sharma", "teacher_id": "t1", "department_id": "cse"}
ADMIN = {"role": "admin", "name": "Principal", "teacher_id": None}
PLATFORM = {"role": "platform", "name": "Platform owner", "teacher_id": None}
