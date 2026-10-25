"""Super Admin (platform owner): sees every college, manages plan / pause / read-only, never college data."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


def login(c, email, password="demo1234"):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_only_the_platform_owner_sees_the_platform(client):
    owner, me = login(client, "owner@demo.timetabl.ai")
    assert me["platform_owner"] and me["memberships"] == []
    admin, me_admin = login(client, "admin@demo.timetabl.ai")
    assert not me_admin["platform_owner"]
    assert client.get("/api/platform/overview", headers=admin).status_code == 404
    out = client.get("/api/platform/overview", headers=owner).json()
    demo = next(x for x in out["items"] if x["id"] == "demo")
    assert demo["is_demo"] and demo["students"] == 720 and demo["departments"] == 4 and demo["plan"] == "trial"
    assert out["colleges"] >= 1 and out["students"] >= 720
    # The platform owner is not a member of any college: college data stays out of reach.
    assert client.get("/api/orgs/demo/college", headers=owner).status_code == 404


def test_pause_and_read_only_are_enforced(client):
    owner, _ = login(client, "owner@demo.timetabl.ai")
    r = client.post("/api/auth/signup", json={"name": "Meera Iyer", "email": "meera@paused.edu", "password": "longenough",
                                              "college_name": "Paused College"})
    assert r.status_code == 201, r.text
    mine = {"Authorization": f"Bearer {r.json()['token']}"}
    org = r.json()["memberships"][0]["org_id"]
    item = next(x for x in client.get("/api/platform/overview", headers=owner).json()["items"] if x["id"] == org)
    assert item["stage"] == "Setting up" and item["accounts"] == 1

    # Read-only: viewing works, changing doesn't.
    r = client.patch(f"/api/platform/colleges/{org}", headers=owner, json={"status": "read_only", "plan": "pro"})
    assert r.status_code == 200 and r.json()["plan"] == "pro" and r.json()["status"] == "read_only"
    assert client.get(f"/api/orgs/{org}/college", headers=mine).status_code == 200
    blocked = client.post(f"/api/orgs/{org}/load-sample", headers=mine)
    assert blocked.status_code == 403 and "read-only" in blocked.json()["detail"]

    # Paused: members can't open it; outsiders still get the same 404 as before (no tenant leak).
    client.patch(f"/api/platform/colleges/{org}", headers=owner, json={"status": "paused"})
    r = client.get(f"/api/orgs/{org}/college", headers=mine)
    assert r.status_code == 403 and "paused" in r.json()["detail"]
    admin, _ = login(client, "admin@demo.timetabl.ai")
    assert client.get(f"/api/orgs/{org}/college", headers=admin).status_code == 404

    client.patch(f"/api/platform/colleges/{org}", headers=owner, json={"status": "active"})
    assert client.post(f"/api/orgs/{org}/load-sample", headers=mine).status_code == 200
    item = next(x for x in client.get("/api/platform/overview", headers=owner).json()["items"] if x["id"] == org)
    assert item["stage"] in ("Ready to generate", "Collecting data") and item["sections"] == 12


def test_bad_values_and_the_demo_stay_safe(client):
    owner, _ = login(client, "owner@demo.timetabl.ai")
    assert client.patch("/api/platform/colleges/demo", headers=owner, json={"status": "paused"}).status_code == 422
    assert client.patch("/api/platform/colleges/demo", headers=owner, json={"plan": "gold"}).status_code == 422
    assert client.patch("/api/platform/colleges/nope", headers=owner, json={"plan": "pro"}).status_code == 404
    admin, _ = login(client, "admin@demo.timetabl.ai")
    assert client.patch("/api/platform/colleges/demo", headers=admin, json={"plan": "pro"}).status_code == 404
