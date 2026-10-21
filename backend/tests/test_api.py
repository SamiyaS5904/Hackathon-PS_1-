"""API tests: login, tenant isolation, role permissions, generate, edit, one-day changes.

One generated demo timetable is shared by the whole module to keep the suite fast.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

PW = "demo1234"
DEMO_CLASSES = 232 + 6  # regular classes + open elective (3 groups x 2 meetings)
WEEKDAY_DATE = {"Mon": "2026-10-19", "Tue": "2026-10-20", "Wed": "2026-10-21", "Thu": "2026-10-22", "Fri": "2026-10-23"}


def login(client, email, password=PW):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        admin = login(c, "admin@demo.timetabl.ai")
        job = c.post("/api/orgs/demo/timetable/generate", json={"time_limit": 25}, headers=admin).json()
        for _ in range(120):
            st = c.get(f"/api/orgs/demo/jobs/{job['id']}", headers=admin).json()
            if st["status"] != "running":
                break
            time.sleep(1)
        assert st["status"] == "done", st
        yield c


@pytest.fixture(scope="module")
def admin(client):
    return login(client, "admin@demo.timetabl.ai")


def test_login_errors_and_me(client):
    bad = client.post("/api/auth/login", json={"email": "admin@demo.timetabl.ai", "password": "nope"})
    assert bad.status_code == 401
    assert client.get("/api/orgs/demo/college").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    me = client.get("/api/me", headers=login(client, "admin@demo.timetabl.ai")).json()
    assert me["memberships"][0]["role"] == "admin" and me["memberships"][0]["org_id"] == "demo"


def test_admin_reads_everything(client, admin):
    out = client.get("/api/orgs/demo/timetable", headers=admin).json()
    assert out["violations"] == [] and len(out["timetable"]["sessions"]) == DEMO_CLASSES
    assert len(client.get("/api/orgs/demo/college", headers=admin).json()["students"]) == 720


def test_new_college_is_isolated(client, admin):
    r = client.post("/api/auth/signup", json={"name": "Asha Rao", "email": "asha@newcollege.edu",
                                               "password": "longenough", "college_name": "New College"})
    assert r.status_code == 201, r.text
    mine = {"Authorization": f"Bearer {r.json()['token']}"}
    org = r.json()["memberships"][0]["org_id"]
    assert org == "new-college"
    # Each admin only reaches their own college; outsiders get a plain 404.
    assert client.get("/api/orgs/demo/timetable", headers=mine).status_code == 404
    assert client.get(f"/api/orgs/{org}/college", headers=admin).status_code == 404
    pre = client.get(f"/api/orgs/{org}/precheck", headers=mine).json()
    assert pre["problems"] and "No classes" in pre["problems"][0]
    sample = client.post(f"/api/orgs/{org}/load-sample", headers=mine)
    assert sample.status_code == 200 and len(sample.json()["sections"]) == 12
    again = client.post("/api/auth/signup", json={"name": "X", "email": "asha@newcollege.edu",
                                                   "password": "longenough", "college_name": "Y"})
    assert again.status_code == 409


def test_student_sees_only_own_section_and_cannot_edit(client):
    st = login(client, "cse3a.01@demo.timetabl.ai")
    sessions = client.get("/api/orgs/demo/timetable", headers=st).json()["timetable"]["sessions"]
    assert sessions and all("cse-3a" in s["section_ids"] for s in sessions)
    assert all(s["batch_id"] in (None, "cse-3a-b1") for s in sessions)  # student 01 is in batch B1
    college = client.get("/api/orgs/demo/college", headers=st).json()
    assert [s["email"] for s in college["students"]] == ["cse3a.01@demo.timetabl.ai"]  # nobody else's details
    s = sessions[0]
    assert client.get(f"/api/orgs/demo/timetable/sessions/{s['id']}/options", headers=st).status_code == 403
    assert client.post("/api/orgs/demo/timetable/generate", json={}, headers=st).status_code == 403
    assert client.get("/api/orgs/demo/audit", headers=st).status_code == 403


def test_teacher_one_day_change_own_lecture_only(client, admin):
    all_sessions = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["sessions"]
    mine = next(s for s in all_sessions if s["teacher_id"] == "t-anita")  # Dr. Anita Sharma
    other = next(s for s in all_sessions if s["teacher_id"] != "t-anita")
    t = login(client, "anita.sharma@demo.timetabl.ai")
    # Permanent change: needs the Coordinator.
    r = client.get(f"/api/orgs/demo/timetable/sessions/{mine['id']}/options", headers=t)
    assert r.status_code == 403 and "Coordinator" in r.json()["detail"]
    # Not their lecture at all.
    r = client.post("/api/orgs/demo/overrides", headers=t,
                    json={"session_id": other["id"], "date": WEEKDAY_DATE[other["day"]], "kind": "cancel"})
    assert r.status_code == 403
    # One-day cancel of their own lecture: instant.
    r = client.post("/api/orgs/demo/overrides", headers=t, json={
        "session_id": mine["id"], "date": WEEKDAY_DATE[mine["day"]], "kind": "cancel", "reason": "Conference"})
    assert r.status_code == 201, r.text
    audit = client.get("/api/orgs/demo/audit", headers=admin).json()
    assert audit[0]["source"] == "teacher" and audit[0]["actor"] == "Dr. Anita Sharma"


def test_coordinator_limited_to_own_department(client, admin):
    all_sessions = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["sessions"]
    cse = next(s for s in all_sessions if s["section_ids"] == ["cse-2a"])
    ece = next(s for s in all_sessions if s["section_ids"] == ["ece-2a"])
    co = login(client, "cse.coordinator@demo.timetabl.ai")
    assert client.get(f"/api/orgs/demo/timetable/sessions/{cse['id']}/options", headers=co).status_code == 200
    assert client.get(f"/api/orgs/demo/timetable/sessions/{ece['id']}/options", headers=co).status_code == 403


def test_invites(client, admin):
    co = login(client, "cse.coordinator@demo.timetabl.ai")
    r = client.post("/api/orgs/demo/invites", headers=co,
                    json={"email": "x@y.edu", "role": "coordinator", "department_id": "cse"})
    assert r.status_code == 403
    r = client.post("/api/orgs/demo/invites", headers=co,
                    json={"email": "x@y.edu", "role": "teacher", "department_id": "ece"})
    assert r.status_code == 403
    inv = client.post("/api/orgs/demo/invites", headers=co,
                      json={"email": "new.teacher@demo.timetabl.ai", "role": "teacher", "department_id": "cse"})
    assert inv.status_code == 201, inv.text
    token = inv.json()["token"]
    assert client.get(f"/api/invites/{token}").json()["role"] == "teacher"
    assert client.post(f"/api/invites/{token}/accept", json={"name": "New Teacher", "password": "short"}).status_code == 422
    acc = client.post(f"/api/invites/{token}/accept", json={"name": "New Teacher", "password": "longenough1"})
    assert acc.status_code == 200 and acc.json()["memberships"][0]["role"] == "teacher"
    assert client.post(f"/api/invites/{token}/accept", json={"password": "longenough1"}).status_code == 422
    names = [m["name"] for m in client.get("/api/orgs/demo/members", headers=admin).json()]
    assert "New Teacher" in names


def test_admin_edit_apply_undo(client, admin):
    sessions = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["sessions"]
    # "repair" (amber) means other classes must shift; some such moves have no clash-free answer,
    # so try amber slots until one can be repaired, like a user would.
    proposal = target = s = None
    for s in sessions:
        if s["elective_slot_id"]:
            continue
        opts = client.get(f"/api/orgs/demo/timetable/sessions/{s['id']}/options", headers=admin).json()
        for target in [o for o in opts if o["status"] == "repair"][:3]:
            body = {"session_id": s["id"], "day": target["day"], "start_period": target["start_period"]}
            r = client.post("/api/orgs/demo/proposals", json=body, headers=admin)
            if r.status_code == 201:
                proposal = r.json()
                break
            assert r.status_code == 422, r.text  # refused with a reason, never an error
        if proposal:
            break
    assert proposal, "expected at least one repairable move"
    assert proposal["changes"][0]["session_id"] == s["id"]
    # Someone else can't apply your proposal.
    co = login(client, "cse.coordinator@demo.timetabl.ai")
    assert client.post(f"/api/orgs/demo/proposals/{proposal['id']}/apply", headers=co).status_code == 403
    applied = client.post(f"/api/orgs/demo/proposals/{proposal['id']}/apply", headers=admin).json()
    assert applied["violations"] == []
    moved = next(x for x in applied["timetable"]["sessions"] if x["id"] == s["id"])
    assert (moved["day"], moved["start_period"]) == (target["day"], target["start_period"])
    audit = client.get("/api/orgs/demo/audit", headers=admin).json()
    assert audit[0]["source"] == "drag" and audit[0]["can_undo"]
    undone = client.post("/api/orgs/demo/audit/undo", headers=admin).json()
    back = next(x for x in undone["timetable"]["sessions"] if x["id"] == s["id"])
    assert (back["day"], back["start_period"]) == (s["day"], s["start_period"])
    assert client.post(f"/api/orgs/demo/proposals/{proposal['id']}/apply", headers=admin).status_code == 409


def test_state_survives_restart(client, admin):
    """Timetable and audit are persisted: a fresh load from the database sees them."""
    from app.store import Store

    fresh = Store()
    fresh.load()
    st = fresh.org("demo")
    assert st.timetable is not None and len(st.timetable.sessions) == DEMO_CLASSES
    assert st.audit and st.audit[0].source == "generate"
