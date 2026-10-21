"""Assistant facts: free rooms, teacher now, explain, insights (and who may see them)."""

import time

from fastapi.testclient import TestClient

from app.assist import free_rooms, insights, teacher_now
from app.main import app
from app.models.domain import Holiday
from app.solver.generate import generate
from tests.conftest import tiny_college

MONDAY = "2026-10-19"


def test_free_rooms_and_teacher_now_follow_the_real_day():
    c = tiny_college()
    tt = generate(c, time_limit=10)
    s = next(x for x in tt.sessions if x.day == "Mon")
    busy_room = {r.venue_id for r in free_rooms(c, tt, MONDAY, s.start)}
    assert s.venue_id not in busy_room
    now = teacher_now(c, tt, s.teacher_id, MONDAY, s.start)
    assert now.status == "teaching" and now.until == s.end
    c.holidays = [Holiday(date=MONDAY, label="Holiday")]
    assert teacher_now(c, tt, s.teacher_id, MONDAY, s.start).status == "holiday"


def test_insights_always_include_quality():
    c = tiny_college()
    tt = generate(c, time_limit=10)
    out = insights(c, tt)
    assert out and out[0].kind == "quality" and all(i.ask for i in out)


def test_assist_endpoints_permissions():
    with TestClient(app) as client:
        def login(email):
            r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
            return {"Authorization": f"Bearer {r.json()['token']}"}

        admin = login("admin@demo.timetabl.ai")
        if client.get("/api/orgs/demo/timetable", headers=admin).status_code == 404 or \
                client.get("/api/orgs/demo/timetable", headers=admin).json()["stale"]:
            job = client.post("/api/orgs/demo/timetable/generate", headers=admin, json={"time_limit": 25}).json()
            for _ in range(120):
                if client.get(f"/api/orgs/demo/jobs/{job['id']}", headers=admin).json()["status"] != "running":
                    break
                time.sleep(1)
        st = login("cse3a.01@demo.timetabl.ai")
        rooms = client.get(f"/api/orgs/demo/free-rooms?date={MONDAY}&at=11:00", headers=st)
        assert rooms.status_code == 200 and all("name" in r for r in rooms.json())
        assert client.get(f"/api/orgs/demo/teachers/t-anita/now?date={MONDAY}&at=10:00", headers=st).status_code == 200
        mine = client.get("/api/orgs/demo/timetable", headers=st).json()["timetable"]["sessions"]
        assert client.get(f"/api/orgs/demo/timetable/sessions/{mine[0]['id']}/explain", headers=st).status_code == 200
        everyone = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["sessions"]
        other = next(s for s in everyone if "cse-3a" not in s["section_ids"])
        assert client.get(f"/api/orgs/demo/timetable/sessions/{other['id']}/explain", headers=st).status_code == 404
        assert client.get("/api/orgs/demo/insights", headers=st).status_code == 403
        assert client.get("/api/orgs/demo/insights", headers=admin).status_code == 200
