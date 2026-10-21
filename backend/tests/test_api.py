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
