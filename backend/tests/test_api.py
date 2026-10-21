"""API smoke tests (in-memory store)."""

import time

from fastapi.testclient import TestClient

from app.main import app


def test_generate_and_read_timetable():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"ok": True}
        college = client.get("/api/orgs/demo/college").json()
        assert len(college["sections"]) == 12
        assert client.get("/api/orgs/demo/precheck").json()["problems"] == []
        assert client.get("/api/orgs/nope/college").status_code == 404

        job = client.post("/api/orgs/demo/timetable/generate", json={"time_limit": 30}).json()
        assert client.post("/api/orgs/demo/timetable/generate", json={}).status_code == 409
        for _ in range(120):
            status = client.get(f"/api/orgs/demo/jobs/{job['id']}").json()
            if status["status"] != "running":
                break
            time.sleep(1)
        assert status["status"] == "done", status

        out = client.get("/api/orgs/demo/timetable").json()
        assert out["violations"] == []
        assert out["timetable"]["sessions"]
        assert 0 <= out["quality"]["score"] <= 100

        # Stage 3: move a class through the API, apply, check audit, undo.
        sessions = out["timetable"]["sessions"]
        target = None
        for s in sessions:
            opts = client.get(f"/api/orgs/demo/timetable/sessions/{s['id']}/options").json()
            target = next((o for o in opts if o["status"] == "repair"), None)
            if target:
                break
        assert target, "expected a slot where other classes must shift"
        r = client.post("/api/orgs/demo/proposals",
                        json={"session_id": s["id"], "day": target["day"], "start_period": target["start_period"]})
        assert r.status_code == 201, r.text
        proposal = r.json()
        assert proposal["changes"] and proposal["changes"][0]["session_id"] == s["id"]

        discard = client.post("/api/orgs/demo/proposals",
                              json={"session_id": s["id"], "day": target["day"], "start_period": target["start_period"]})
        assert client.delete(f"/api/orgs/demo/proposals/{discard.json()['id']}").status_code == 204

        applied = client.post(f"/api/orgs/demo/proposals/{proposal['id']}/apply").json()
        assert applied["violations"] == []
        moved = next(x for x in applied["timetable"]["sessions"] if x["id"] == s["id"])
        assert (moved["day"], moved["start_period"]) == (target["day"], target["start_period"])

        audit = client.get("/api/orgs/demo/audit").json()
        assert audit[0]["source"] == "drag" and audit[0]["can_undo"]
        undone = client.post("/api/orgs/demo/audit/undo").json()
        back = next(x for x in undone["timetable"]["sessions"] if x["id"] == s["id"])
        assert (back["day"], back["start_period"]) == (s["day"], s["start_period"])
        # A stale proposal can't be applied after the timetable changed.
        assert client.post(f"/api/orgs/demo/proposals/{proposal['id']}/apply").status_code == 409
