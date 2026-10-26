"""Room booking API on the demo college: who may book, who approves, notifications, college isolation."""

import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store

PW = "demo1234"


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _working_day(days_ahead: int = 8) -> str:
    """A working, non-holiday date in the future (the API reads the real clock)."""
    college = store.org("demo").college
    holidays = {h.date for h in college.holidays}
    d = datetime.date.today() + datetime.timedelta(days=days_ahead)
    while d.strftime("%a") not in college.days or d.isoformat() in holidays:
        d += datetime.timedelta(days=1)
    return d.isoformat()


def _titles(client, headers):
    return [n["title"] for n in client.get("/api/orgs/demo/notifications", headers=headers).json()["items"]]


def test_teacher_books_another_departments_room_and_its_coordinator_decides(client):
    teacher = login(client, "harpreet.kaur@demo.timetabl.ai")  # CSE
    d = _working_day()
    free = client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=15:10&end=16:50", headers=teacher)
    assert free.status_code == 200, free.text
    college = store.org("demo").college
    owner = {v.id: v.department_id for v in college.venues}
    room = next(r for r in free.json() if owner[r["venue_id"]] == "ece")
    assert room["approver"] == "ECE Coordinator"
    r = client.post("/api/orgs/demo/venue-events", headers=teacher, json={
        "venue_id": room["venue_id"], "date": d, "start": "15:10", "end": "16:50", "title": "Robotics demo",
        "club": "Robotics Club"})
    assert r.status_code == 201, r.text
    ev = r.json()["event"]
    assert ev["status"] == "pending" and not ev["can_decide"] and ev["can_cancel"]
    # The room is no longer offered to anyone else, and a second booking is refused.
    other = login(client, "kavita.rao@demo.timetabl.ai")
    again = client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=16:00&end=16:50", headers=other).json()
    assert room["venue_id"] not in {x["venue_id"] for x in again}
    dup = client.post("/api/orgs/demo/venue-events", headers=other, json={
        "venue_id": room["venue_id"], "date": d, "start": "16:00", "end": "16:50", "title": "Talk"})
    assert dup.status_code == 422
    # The ECE Coordinator hears about it and decides; the CSE Coordinator can't.
    ece = login(client, "ece.coordinator@demo.timetabl.ai")
    cse = login(client, "cse.coordinator@demo.timetabl.ai")
    assert any("Robotics demo" in t for t in _titles(client, ece))
    assert not any("Robotics demo" in t for t in _titles(client, cse))
    assert client.post(f"/api/orgs/demo/venue-events/{ev['id']}/approve", headers=cse).status_code == 404
    review = client.get("/api/orgs/demo/venue-events", headers=ece).json()["to_review"]
    assert [e["id"] for e in review] == [ev["id"]] and review[0]["can_decide"]
    ok = client.post(f"/api/orgs/demo/venue-events/{ev['id']}/approve", headers=ece)
    assert ok.status_code == 200 and ok.json()["event"]["status"] == "approved"
    assert any(t.startswith("Room booked") for t in _titles(client, teacher))
    assert client.post(f"/api/orgs/demo/venue-events/{ev['id']}/approve", headers=ece).status_code == 409
    mine = client.get("/api/orgs/demo/venue-events", headers=teacher).json()["mine"]
    assert [e["status"] for e in mine if e["id"] == ev["id"]] == ["approved"]
    # Cancelling frees the room; the Coordinator is told.
    assert client.post(f"/api/orgs/demo/venue-events/{ev['id']}/cancel", headers=teacher).status_code == 200
    assert any("cancelled" in t for t in _titles(client, ece))


def test_shared_rooms_go_to_the_admin_and_declines_are_explained(client):
    teacher = login(client, "kavita.rao@demo.timetabl.ai")
    admin = login(client, "admin@demo.timetabl.ai")
    d = _working_day(9)
    college = store.org("demo").college
    shared = {v.id for v in college.venues if v.department_id is None}
    free = client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=11:00&end=11:50", headers=teacher).json()
    room = next(r for r in free if r["venue_id"] in shared)
    assert room["approver"] == "College Admin"
    ev = client.post("/api/orgs/demo/venue-events", headers=teacher, json={
        "venue_id": room["venue_id"], "date": d, "start": "11:00", "end": "11:50", "title": "Quiz"}).json()["event"]
    no = client.post(f"/api/orgs/demo/venue-events/{ev['id']}/decline", headers=admin, json={"note": "Exam that day"})
    assert no.status_code == 200 and no.json()["event"]["status"] == "declined"
    assert any("declined" in t for t in _titles(client, teacher))


def test_students_and_other_colleges_get_nothing(client):
    student = login(client, "cse3a.01@demo.timetabl.ai")
    d = _working_day()
    assert client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=11:00&end=11:50",
                      headers=student).status_code == 403
    assert client.get("/api/orgs/demo/venue-events", headers=student).status_code == 403
    r = client.post("/api/auth/signup", json={"name": "Ravi Kumar", "email": "ravi@othercollege.edu",
                                               "password": "longenough", "college_name": "Other Events College"})
    assert r.status_code == 201, r.text
    outsider = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/orgs/demo/venue-events", headers=outsider).status_code == 404
    assert client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=11:00&end=11:50",
                      headers=outsider).status_code == 404
    teacher = login(client, "harpreet.kaur@demo.timetabl.ai")
    free = client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=09:00&end=09:50", headers=teacher)
    bad = client.get(f"/api/orgs/demo/venue-events/free?date={d}&start=10:00&end=09:00", headers=teacher)
    assert free.status_code in (200, 422) and bad.status_code == 422
