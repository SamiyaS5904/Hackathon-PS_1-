"""Rule cards (no classes in a window, max periods a day) and teacher block times."""

import time

from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import Rule
from app.solver.generate import generate
from app.validator.check import validate
from tests.conftest import tiny_college


def test_must_window_rule_is_obeyed_and_checked():
    c = tiny_college()
    c.rules = [Rule(id="r1", name="Nothing after 13:00", kind="no_classes", after="13:00")]
    tt = generate(c, time_limit=10)
    assert tt.status in ("optimal", "feasible"), tt.messages
    assert all(s.end <= "13:00" for s in tt.sessions)
    assert validate(c, tt.sessions, tt.lunches) == []
    moved = tt.sessions[0].model_copy(update={"start_period": 5, "start": "14:00", "end": "15:00"})
    assert "rule_broken" in {v.type for v in validate(c, [moved, *tt.sessions[1:]], tt.lunches)}


def test_must_max_per_day_rule():
    c = tiny_college()
    c.rules = [Rule(id="r1", name="Max 3 a day", kind="max_per_day", max_periods=3)]
    tt = generate(c, time_limit=10)
    assert validate(c, tt.sessions, tt.lunches) == []
    for day in c.days:
        for b in ("b1", "b2"):
            periods = sum(s.length for s in tt.sessions if s.day == day and s.batch_id in (None, b))
            assert periods <= 3


def test_try_rule_bends_instead_of_failing():
    c = tiny_college()
    # Impossible as a Must (no classes at all on any day), fine as a preference.
    c.rules = [Rule(id="r1", name="Prefer no classes", kind="no_classes", mode="try", weight=2, after="00:00")]
    tt = generate(c, time_limit=10)
    assert tt.status in ("optimal", "feasible") and validate(c, tt.sessions, tt.lunches) == []


def test_rules_api_permissions_and_block_times():
    with TestClient(app) as client:
        def login(email):
            r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
            return {"Authorization": f"Bearer {r.json()['token']}"}

        admin, co = login("admin@demo.timetabl.ai"), login("cse.coordinator@demo.timetabl.ai")
        college_rule = {"id": "fri", "name": "Short Friday", "kind": "no_classes", "days": ["Fri"], "after": "16:20"}
        r = client.put("/api/orgs/demo/rules", headers=admin, json={"rules": [college_rule]})
        assert r.status_code == 200, r.text
        dept_rule = {"id": "cse-max", "name": "CSE max 5", "kind": "max_per_day", "max_periods": 5,
                     "department_id": "cse", "mode": "try", "weight": 4}
        ok = client.put("/api/orgs/demo/rules", headers=co, json={"rules": [college_rule, dept_rule]})
        assert ok.status_code == 200, ok.text
        no = client.put("/api/orgs/demo/rules", headers=co, json={"rules": [dept_rule]})  # deleting a college rule
        assert no.status_code == 403
        bad = client.put("/api/orgs/demo/rules", headers=admin, json={"rules": [{**dept_rule, "max_periods": None}]})
        assert bad.status_code == 422

        # Block times need a timetable to check against: generate one.
        job = client.post("/api/orgs/demo/timetable/generate", headers=admin, json={"time_limit": 25}).json()
        for _ in range(120):
            if client.get(f"/api/orgs/demo/jobs/{job['id']}", headers=admin).json()["status"] != "running":
                break
            time.sleep(1)
        sessions = client.get("/api/orgs/demo/timetable", headers=admin).json()["timetable"]["sessions"]
        assert not [s for s in sessions if s["day"] == "Fri" and s["end"] > "16:20"]  # the Must rule held
        t = login("anita.sharma@demo.timetabl.ai")
        mine = [s for s in sessions if s["teacher_id"] == "t-anita"]
        clash = mine[0]
        r = client.put("/api/orgs/demo/me/blocked", headers=t,
                       json={"blocked": [{"day": clash["day"], "start": clash["start"], "end": clash["end"]}]})
        assert r.status_code == 409 and "Coordinator" in r.json()["detail"]
        busy = {(s["day"], s["start"]) for s in mine}
        free = next(d for d in ["Mon", "Tue", "Wed", "Thu", "Fri"] if (d, "14:10") not in busy)
        r = client.put("/api/orgs/demo/me/blocked", headers=t,
                       json={"blocked": [{"day": free, "start": "14:10", "end": "15:00"}]})
        assert r.status_code == 200, r.text
        assert not client.get("/api/orgs/demo/timetable", headers=admin).json()["stale"]  # still valid
        assert client.put("/api/orgs/demo/me/blocked", headers=admin, json={"blocked": []}).status_code == 403
