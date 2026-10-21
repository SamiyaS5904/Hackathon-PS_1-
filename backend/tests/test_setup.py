"""Setting up a new college from scratch through the API, the way an Admin and Coordinator would."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


def auth(r):
    assert r.status_code in (200, 201), r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


SHIFT = {
    "id": "day", "name": "Day",
    "periods": [{"start": a, "end": b} for a, b in [("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00"),
                                                    ("12:00", "13:00"), ("13:00", "14:00"), ("14:00", "15:00")]],
    "year_breaks": [], "lunch": {"window_start": "12:00", "window_end": "14:00"},
}


def cse_data(teacher_for_maths=None):
    sec = {"id": "cse-1a", "name": "CSE-1A", "department_id": "cse", "year": 1, "strength": 40, "shift_id": "day",
           "batches": [{"id": "cse-1a-b1", "name": "B1", "strength": 20}, {"id": "cse-1a-b2", "name": "B2", "strength": 20}]}
    return {
        "sections": [sec],
        "teachers": [
            {"id": "t-a", "name": "Dr. A", "department_id": "cse", "shift_ids": ["day"], "max_per_day": 4, "blocked": []},
            {"id": "t-b", "name": "Dr. B", "department_id": "cse", "shift_ids": ["day"], "max_per_day": 4, "blocked": []},
        ],
        "subjects": [
            {"id": "ma", "code": "MA", "name": "Maths", "department_id": "cse", "year": 1, "lectures_per_week": 3},
            {"id": "cs", "code": "CS", "name": "Programming", "department_id": "cse", "year": 1,
             "lectures_per_week": 2, "labs_per_week": 1, "lab_tag": "computers"},
        ],
        "venues": [
            {"id": "r1", "name": "Room 1", "type": "lecture", "capacity": 45, "tags": [], "department_id": "cse"},
            {"id": "lab", "name": "Lab", "type": "lab", "capacity": 25, "tags": ["computers"], "department_id": "cse"},
        ],
        "allotments": [
            {"id": "c1", "subject_id": "ma", "teacher_id": teacher_for_maths, "kind": "lecture", "section_ids": ["cse-1a"]},
            {"id": "c2", "subject_id": "cs", "teacher_id": None, "kind": "lecture", "section_ids": ["cse-1a"]},
            {"id": "c3", "subject_id": "cs", "teacher_id": None, "kind": "lab", "section_ids": ["cse-1a"],
             "batch_id": "cse-1a-b1"},
            {"id": "c4", "subject_id": "cs", "teacher_id": None, "kind": "lab", "section_ids": ["cse-1a"],
             "batch_id": "cse-1a-b2"},
        ],
        "teacher_subjects": [
            {"teacher_id": "t-a", "subject_id": "ma", "preference": 1},
            {"teacher_id": "t-b", "subject_id": "cs", "preference": 1},
        ],
        "students": [{"id": f"s{i}", "roll_no": f"CSE1A{i:02d}", "name": f"Student {i}", "email": f"s{i}@sunrise.edu",
                      "section_id": "cse-1a", "batch_id": "cse-1a-b1" if i <= 20 else "cse-1a-b2"} for i in range(1, 41)],
    }


@pytest.fixture(scope="module")
def setup():
    with TestClient(app) as c:
        admin = auth(c.post("/api/auth/signup", json={"name": "Principal", "email": "principal@sunrise.edu",
                                                      "password": "verysecret", "college_name": "Sunrise College"}))
        org = c.get("/api/me", headers=admin).json()["memberships"][0]["org_id"]
        yield c, admin, f"/api/orgs/{org}"


def test_full_setup_flow(setup):
    c, admin, base = setup
    r = c.put(f"{base}/departments", headers=admin, json={
        "departments": [{"id": "cse", "name": "Computer Science", "short": "CSE"},
                        {"id": "me", "name": "Mechanical", "short": "ME"}],
        "shared_venues": [{"id": "hall", "name": "Hall", "type": "seminar", "capacity": 120, "tags": []}]})
    assert r.status_code == 200, r.text
    r = c.put(f"{base}/settings", headers=admin, json={
        "days": ["Mon", "Tue", "Wed"], "lab_periods": 2, "shifts": [SHIFT],
        "holidays": [{"date": "2026-10-21", "label": "Founders' Day"}],
        "semester_start": "2026-08-01", "semester_end": "2026-12-15"})
    assert r.status_code == 200, r.text

    # Coordinator enters the department: teachers for programming left blank on purpose.
    r = c.put(f"{base}/departments/cse/data", headers=admin, json=cse_data())
    assert r.status_code == 200, r.text
    assert any("no teacher yet" in p for p in r.json()["problems"])
    assert c.post(f"{base}/departments/cse/ready", headers=admin, json={"ready": True}).status_code == 422

    sug = c.post(f"{base}/departments/cse/suggest", headers=admin, json={}).json()
    picks = {s["allotment_id"]: s["teacher_id"] for s in sug["suggestions"]}
    assert picks == {"c1": "t-a", "c2": "t-b", "c3": "t-b", "c4": "t-b"}
    r = c.put(f"{base}/departments/cse/allotments", headers=admin, json={"assignments": picks})
    assert r.status_code == 200 and r.json()["problems"] == []
    r = c.post(f"{base}/departments/cse/ready", headers=admin, json={"ready": True})
    assert r.status_code == 200
    ready = {d["department_id"]: d for d in c.get(f"{base}/readiness", headers=admin).json()}
    assert ready["cse"]["ready"] and ready["cse"]["classes"] == 4 and ready["cse"]["students"] == 40
    assert not ready["me"]["ready"]

    job = c.post(f"{base}/timetable/generate", headers=admin, json={"time_limit": 10}).json()
    for _ in range(60):
        st = c.get(f"{base}/jobs/{job['id']}", headers=admin).json()
        if st["status"] != "running":
            break
        time.sleep(0.5)
    assert st["status"] == "done", st
    out = c.get(f"{base}/timetable", headers=admin).json()
    assert out["violations"] == [] and not out["stale"] and len(out["timetable"]["sessions"]) == 3 + 2 + 2

    # Holiday: no classes that date; one-day moves onto it are refused.
    wk = c.get(f"{base}/timetable/week?start=2026-10-19", headers=admin).json()
    assert next(d for d in wk["days"] if d["date"] == "2026-10-21")["holiday"] == "Founders' Day"
    assert not any(o["date"] == "2026-10-21" for o in wk["occurrences"])

    # Students from the list log in with email + roll number the first time.
    st = auth(c.post("/api/auth/login", json={"email": "s21@sunrise.edu", "password": "CSE1A21"}))
    mine = c.get(f"{base}/timetable", headers=st).json()["timetable"]["sessions"]
    assert mine and all(s["batch_id"] in (None, "cse-1a-b2") for s in mine)
    assert c.post("/api/auth/login", json={"email": "s21@sunrise.edu", "password": "wrong"}).status_code == 401

    # Changing data marks the timetable as out of date and blocks edits until it's regenerated.
    data = c.get(f"{base}/departments/cse/data", headers=admin).json()
    data["teachers"][0]["max_per_day"] = 3
    assert c.put(f"{base}/departments/cse/data", headers=admin, json=data).status_code == 200
    out = c.get(f"{base}/timetable", headers=admin).json()
    assert out["stale"]
    sid = out["timetable"]["sessions"][0]["id"]
    assert c.get(f"{base}/timetable/sessions/{sid}/options", headers=admin).status_code == 409
    assert not {d["department_id"]: d for d in c.get(f"{base}/readiness", headers=admin).json()}["cse"]["ready"]


def test_structure_errors_and_permissions(setup):
    c, admin, base = setup
    bad = cse_data("t-a")
    bad["sections"].append(dict(bad["sections"][0]))  # duplicate section id
    r = c.put(f"{base}/departments/cse/data", headers=admin, json=bad)
    assert r.status_code == 422 and "same id" in r.json()["detail"]

    wrong_dept = cse_data("t-a")
    wrong_dept["teachers"][0]["department_id"] = "me"
    assert c.put(f"{base}/departments/cse/data", headers=admin, json=wrong_dept).status_code == 422

    bad_settings = {"days": ["Mon"], "lab_periods": 2, "shifts": [{**SHIFT, "periods": [{"start": "10:00", "end": "09:00"}]}]}
    assert c.put(f"{base}/settings", headers=admin, json=bad_settings).status_code == 422

    # The ME Coordinator can't touch CSE data, nor college settings.
    inv = c.post(f"{base}/invites", headers=admin,
                 json={"email": "me.co@sunrise.edu", "role": "coordinator", "department_id": "me"}).json()
    me_co = auth(c.post(f"/api/invites/{inv['token']}/accept", json={"name": "ME Co", "password": "longenough"}))
    assert c.get(f"{base}/departments/cse/data", headers=me_co).status_code == 403
    assert c.get(f"{base}/departments/me/data", headers=me_co).status_code == 200
    assert c.put(f"{base}/settings", headers=me_co, json={"days": ["Mon"], "lab_periods": 2, "shifts": [SHIFT]}).status_code == 403
    r = c.put(f"{base}/departments", headers=admin, json={"departments": [{"id": "me", "name": "Mechanical", "short": "ME"}],
                                                         "shared_venues": []})
    assert r.status_code == 422 and "still have sections" in r.json()["detail"]
