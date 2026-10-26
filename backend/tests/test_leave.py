"""Teacher leave: ask -> approve, cover plan (substitutes ranked, per-year cancel), apply, undo, permissions."""

import time

import pytest
from fastapi.testclient import TestClient

from app.edits.oneday import _day
from app.main import app
from app.store import store
from app.validator.check import validate

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
        r = c.get("/api/orgs/demo/timetable", headers=admin)
        if r.status_code != 200 or r.json()["stale"]:
            job = c.post("/api/orgs/demo/timetable/generate", json={"time_limit": 20}, headers=admin).json()
            for _ in range(120):
                if c.get(f"/api/orgs/demo/jobs/{job['id']}", headers=admin).json()["status"] != "running":
                    break
                time.sleep(1)
        c.post("/api/orgs/demo/timetable/publish", headers=admin)
        yield c


@pytest.fixture(scope="module")
def coord(client):
    return login(client, "cse.coordinator@demo.timetabl.ai")


def _busiest_cse_day(client, h):
    """A CSE teacher and the weekday on which they teach the most classes."""
    college = client.get("/api/orgs/demo/college", headers=h).json()
    cse = {t["id"] for t in college["teachers"] if t["department_id"] == "cse"}
    tt = client.get("/api/orgs/demo/timetable", headers=h).json()["timetable"]
    count = {}
    for s in tt["sessions"]:
        if s["teacher_id"] in cse:
            count[(s["teacher_id"], s["day"])] = count.get((s["teacher_id"], s["day"]), 0) + 1
    (tid, day), _ = max(count.items(), key=lambda kv: kv[1])
    return tid, DATE[day]


def test_plan_covers_with_free_same_subject_teachers_and_applies_cleanly(client, coord):
    tid, d = _busiest_cse_day(client, coord)
    r = client.post("/api/orgs/demo/leaves/plan", headers=coord,
                    json={"teacher_id": tid, "start_date": d, "end_date": d})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["items"] and plan["covered"] + plan["cancelled"] == len(plan["items"])
    subs = [i for i in plan["items"] if i["action"] == "substitute"]
    assert subs, plan["summary"]
    for i in subs:
        assert i["teacher_id"] != tid and i["options"][0]["teacher_id"] == i["teacher_id"]
    # No substitute is booked twice at the same time.
    slots = [(i["teacher_id"], i["date"], i["start"]) for i in subs]
    assert len(slots) == len(set(slots))

    # Per year: cancel one year, keep substitutes for the others.
    year = plan["items"][0]["year"]
    r = client.post("/api/orgs/demo/leaves/plan", headers=coord, json={
        "teacher_id": tid, "start_date": d, "end_date": d, "actions": {str(year): "cancel"}})
    plan2 = r.json()
    assert all(i["action"] == "cancel" for i in plan2["items"] if i["year"] == year)

    choices = [{"session_id": i["session_id"], "date": i["date"], "action": i["action"],
                "teacher_id": i["teacher_id"]} for i in plan2["items"]]
    r = client.post("/api/orgs/demo/leaves/apply", headers=coord, json={
        "teacher_id": tid, "start_date": d, "end_date": d, "reason": "Conference", "choices": choices})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["leave"]["status"] == "approved" and out["leave"]["applied_at"] and out["entry_id"]

    state = store.org("demo")
    tt = state.timetable
    assert not validate(state.college, *_day(state.college, tt, d), check_counts=False)
    kinds = {o.kind for o in tt.overrides if o.date == d}
    assert ("substitute" in kinds) == bool(plan2["covered"])
    week = client.get(f"/api/orgs/demo/timetable/week?start={d}", headers=coord).json()["occurrences"]
    notes = [o["note"] for o in week if o["date"] == d and o.get("substitute_for") == tid]
    assert len(notes) == plan2["covered"] and all(n.startswith("Substitute:") for n in notes)

    # Applying the same leave twice is refused; undo puts everything back.
    again = client.post("/api/orgs/demo/leaves/apply", headers=coord, json={
        "leave_id": out["leave"]["id"], "teacher_id": tid, "start_date": d, "end_date": d, "choices": choices})
    assert again.status_code == 409
    r = client.post("/api/orgs/demo/audit/undo", headers=coord, json={"entry_id": out["entry_id"]})
    assert r.status_code == 200, r.text
    assert not [o for o in store.org("demo").timetable.overrides if o.date == d and o.reason.startswith("Conference")]


def test_teacher_asks_and_coordinator_approves(client, coord):
    teacher = login(client, "anita.sharma@demo.timetabl.ai")
    r = client.post("/api/orgs/demo/leaves", headers=teacher,
                    json={"start_date": DATE["Tue"], "end_date": DATE["Wed"], "reason": "Family function"})
    assert r.status_code == 201, r.text
    lv = r.json()
    assert lv["status"] == "pending"
    mine = client.get("/api/orgs/demo/leaves", headers=teacher).json()
    assert lv["id"] in [x["id"] for x in mine]
    # Dr. Anita teaches in Applied Sciences: the CSE Coordinator neither sees nor decides it; the Admin does.
    assert lv["id"] not in [x["id"] for x in client.get("/api/orgs/demo/leaves", headers=coord).json()]
    assert client.post(f"/api/orgs/demo/leaves/{lv['id']}/decide", headers=coord, json={"approve": True}).status_code == 403
    admin = login(client, "admin@demo.timetabl.ai")
    waiting = client.get("/api/orgs/demo/leaves", headers=admin).json()
    assert any(x["id"] == lv["id"] and x["status"] == "pending" for x in waiting)
    r = client.post(f"/api/orgs/demo/leaves/{lv['id']}/decide", headers=admin, json={"approve": True})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert client.post(f"/api/orgs/demo/leaves/{lv['id']}/decide", headers=admin, json={"approve": False}).status_code == 409


def test_permissions(client, coord):
    admin = login(client, "admin@demo.timetabl.ai")
    college = client.get("/api/orgs/demo/college", headers=admin).json()
    other = next(t["id"] for t in college["teachers"] if t["department_id"] != "cse")
    body = {"teacher_id": other, "start_date": DATE["Mon"], "end_date": DATE["Mon"]}
    assert client.post("/api/orgs/demo/leaves/plan", headers=coord, json=body).status_code == 403
    assert client.post("/api/orgs/demo/leaves/plan", headers=admin, json=body).status_code == 200
    teacher = login(client, "anita.sharma@demo.timetabl.ai")
    assert client.post("/api/orgs/demo/leaves/plan", headers=teacher, json=body).status_code == 403
    assert client.post("/api/orgs/demo/leaves", headers=teacher, json=body).status_code == 403  # not her own
    student = login(client, "cse3a.01@demo.timetabl.ai")
    assert client.get("/api/orgs/demo/leaves", headers=student).status_code == 403
    too_long = {**body, "end_date": "2026-12-30"}
    assert client.post("/api/orgs/demo/leaves/plan", headers=admin, json=too_long).status_code == 422
