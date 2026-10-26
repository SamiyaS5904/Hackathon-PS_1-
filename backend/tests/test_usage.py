"""Assistant cost card: recorded per college, priced, Admin-only, platform owner sees every college."""

from fastapi.testclient import TestClient

from app import usage
from app.main import app


def login(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_usage_is_recorded_priced_and_admin_only():
    with TestClient(app) as c:
        admin = login(c, "admin@demo.timetabl.ai")
        before = c.get("/api/orgs/demo/assistant/usage", headers=admin).json()["month"]["requests"]
        student = login(c, "cse3a.01@demo.timetabl.ai")
        r = c.post("/api/orgs/demo/assistant/usage", headers=student,
                   json={"input": 1_000_000, "output": 100_000, "cache_read": 1_000_000})
        assert r.status_code == 204
        out = c.get("/api/orgs/demo/assistant/usage", headers=admin).json()
        assert out["month"]["requests"] == before + 1
        assert out["today"]["usd"] >= 4 + 2 + 0.2 - 1e-6  # $4 input + $2 output + $0.20 cache read
        assert out["by_day"][-1]["requests"] >= 1 and len(out["by_day"]) == 14
        assert c.get("/api/orgs/demo/assistant/usage", headers=student).status_code == 403
        assert c.get("/api/orgs/other-college/assistant/usage", headers=admin).status_code == 404
        assert "demo" in usage.all_colleges()
