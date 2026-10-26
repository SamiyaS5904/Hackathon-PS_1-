"""Staff home (Today), batch one-day changes, undo of an exact change, setup checklist, problem links."""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

PW = "demo1234"
DATE = {"Mon": "2026-11-02", "Tue": "2026-11-03", "Wed": "2026-11-04", "Thu": "2026-11-05", "Fri": "2026-11-06"}


def login(c, email, password=PW):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        admin = login(c, "admin@demo.timetabl.ai")
        if c.get("/api/orgs/demo/timetable", headers=admin).status_code != 200 or \
                c.get("/api/orgs/demo/timetable", headers=admin).json()["stale"]:
            job = c.post("/api/orgs/demo/timetable/generate", json={"time_limit": 20}, headers=admin).json()
            for _ in range(120):
                if c.get(f"/api/orgs/demo/jobs/{job['id']}", headers=admin).json()["status"] != "running":
                    break
                time.sleep(1)
        c.post("/api/orgs/demo/timetable/publish", headers=admin)
        yield c


@pytest.fixture(scope="module")
def admin(client):
    return login(client, "admin@demo.timetabl.ai")


def _teacher_day(client, admin, dept=None):
    """A teacher (optionally of one department's sections) and a weekday with 2+ of their regular classes."""
    tt = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]
    by = {}
    for s in tt["sessions"]:
        if s["elective_slot_id"] or (dept and not all(x.startswith(dept + "-") for x in s["section_ids"])):
            continue
        by.setdefault((s["teacher_id"], s["day"]), []).append(s)
    return next((k, v) for k, v in by.items() if len(v) >= 2)


def test_teacher_away_in_one_step_shows_on_today_and_undoes_exactly(client, admin):
    (tid, day), classes = _teacher_day(client, admin, "ece")
    d = DATE[day]
    r = client.post("/api/orgs/demo/overrides/batch", headers=admin, json={
        "title": "Teacher away", "changes": [{"session_id": s["id"], "date": d, "kind": "cancel",
                                               "reason": "On leave"} for s in classes]})
    assert r.status_code == 201, r.text
    last = r.json()["timetable"]["last_change"]
    assert last["action"] == "Teacher away" and last["can_undo"]

    today = client.get(f"/api/orgs/demo/today?date={d}", headers=admin).json()
    assert any(a["teacher_id"] == tid for a in today["away"])
    assert {c["session_id"] for c in today["cancelled"]} >= {s["id"] for s in classes}
    assert today["recent"][0]["action"] == "Teacher away" and today["status"]["state"] == "published"

    # A Coordinator sees only their own department; teachers can't open Today.
    cse = client.get(f"/api/orgs/demo/today?date={d}", headers=login(client, "cse.coordinator@demo.timetabl.ai")).json()
    assert not any(c["session_id"] in {s["id"] for s in classes} for c in cse["cancelled"])
    assert client.get("/api/orgs/demo/today", headers=login(client, "anita.sharma@demo.timetabl.ai")).status_code == 403

    # Undo targets exactly this change; an older id is refused.
    assert client.post("/api/orgs/demo/audit/undo", headers=admin, json={"entry_id": "not-the-latest"}).status_code == 409
    assert client.post("/api/orgs/demo/audit/undo", headers=admin, json={"entry_id": last["id"]}).status_code == 200
    today = client.get(f"/api/orgs/demo/today?date={d}", headers=admin).json()
    assert not any(a["teacher_id"] == tid for a in today["away"])


def test_batch_is_all_or_nothing(client, admin):
    (tid, day), classes = _teacher_day(client, admin)
    wrong_day = next(v for k, v in DATE.items() if k != day)
    before = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["overrides"]
    r = client.post("/api/orgs/demo/overrides/batch", headers=admin, json={"changes": [
        {"session_id": classes[0]["id"], "date": DATE[day], "kind": "cancel"},
        {"session_id": classes[1]["id"], "date": wrong_day, "kind": "cancel"}]})
    assert r.status_code == 422 and "Nothing was changed" in r.json()["detail"]
    assert client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["overrides"] == before
    student = login(client, "cse3a.01@demo.timetabl.ai")
    assert client.post("/api/orgs/demo/overrides/batch", headers=student, json={"changes": [
        {"session_id": classes[0]["id"], "date": DATE[day], "kind": "cancel"}]}).status_code in (403, 404)


def test_setup_checklist_and_problem_links(client):
    r = client.post("/api/auth/signup", json={"name": "Ravi Menon", "email": "ravi@checklist.edu",
                                              "password": "longenough", "college_name": "Checklist College"})
    mine = {"Authorization": f"Bearer {r.json()['token']}"}
    org = r.json()["memberships"][0]["org_id"]
    steps = {s["key"]: s for s in client.get(f"/api/orgs/{org}/setup-status", headers=mine).json()["steps"]}
    assert not steps["details"]["done"] and steps["details"]["link"].startswith("/setup")
    assert not steps["departments"]["done"] and "department" in steps["departments"]["missing"].lower()
    settings = client.get(f"/api/orgs/{org}/settings", headers=mine).json()
    assert client.put(f"/api/orgs/{org}/settings", headers=mine, json=settings).status_code == 200
    status = client.get(f"/api/orgs/{org}/setup-status", headers=mine).json()
    assert {s["key"]: s["done"] for s in status["steps"]}["details"] and not status["done"]

    # Problems before generating come with the page where they can be fixed.
    client.post(f"/api/orgs/{org}/load-sample", headers=mine)
    college = client.get(f"/api/orgs/{org}/college", headers=mine).json()
    teacher = college["teachers"][0]
    teacher["max_per_day"] = 1  # far too few periods for their classes
    put = client.put(f"/api/orgs/{org}/departments/{teacher['department_id']}/data", headers=mine,
                     json={**client.get(f"/api/orgs/{org}/departments/{teacher['department_id']}/data",
                                        headers=mine).json(),
                           "teachers": [t if t["id"] != teacher["id"] else teacher
                                        for t in college["teachers"] if t["department_id"] == teacher["department_id"]]})
    assert put.status_code == 200, put.text
    pre = client.get(f"/api/orgs/{org}/precheck", headers=mine).json()
    hit = next(p for p in pre["located"] if teacher["name"] in p["message"])
    assert hit["link"] == f"/departments/{teacher['department_id']}" and "department" in hit["where"]


def test_demo_setup_is_complete_and_timetable_says_who_changed_it(client, admin):
    # Other test modules re-import department data (which un-marks Ready): mark them Ready again first.
    college = client.get("/api/orgs/demo/college", headers=admin).json()
    for d in {s["department_id"] for s in college["sections"]}:
        client.post(f"/api/orgs/demo/departments/{d}/ready", headers=admin, json={"ready": True})
    status = client.get("/api/orgs/demo/setup-status", headers=admin).json()
    assert status["done"], [s for s in status["steps"] if not s["done"]]
    tt = client.get("/api/orgs/demo/timetable", headers=admin).json()
    assert tt["last_change"] and tt["last_change"]["actor"]
    student = client.get("/api/orgs/demo/timetable", headers=login(client, "cse3a.01@demo.timetabl.ai")).json()
    assert student["last_change"] is None  # names of staff stay with staff
