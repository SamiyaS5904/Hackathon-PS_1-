"""The GNDEC demo college is seeded with its accounts, and the Demo page can list its one-click logins."""

from fastapi.testclient import TestClient

from app import accounts
from app.main import app
from app.store import store


def test_gndec_demo_is_seeded_with_logins(monkeypatch):
    monkeypatch.setenv("DEMO_GNDEC", "1")
    with TestClient(app) as c:
        accounts.seed_gndec()
        accounts.seed_gndec()  # twice is harmless
        assert store.org("gndec") is not None and store.org("gndec").is_demo
        r = c.get("/api/demo/gndec/logins")
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["sections"] >= 20 and out["students"] > 1000
        roles = {x["role"] for x in out["logins"]}
        assert roles == {"admin", "coordinator", "teacher", "student"}
        assert any(x.get("section") == "JPAL student" for x in out["logins"])
        for who in [next(x for x in out["logins"] if x["role"] == r) for r in ("admin", "coordinator", "teacher", "student")]:
            login = c.post("/api/auth/login", json={"email": who["email"], "password": "demo1234"})
            assert login.status_code == 200, who
            assert [m["org_id"] for m in login.json()["memberships"]] == ["gndec"]
        assert c.get("/api/demo/demo/logins").status_code == 404  # only the GNDEC demo lists its people
        assert c.get("/api/demo/someone-else/logins").status_code == 404
