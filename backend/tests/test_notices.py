"""Notices on Home: who may post to whom, who sees them, the bell, expiry, college isolation."""

import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app

PW = "demo1234"


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _in(days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _titles(client, headers):
    return [n["title"] for n in client.get("/api/orgs/demo/notices", headers=headers).json()]


def _bell(client, headers):
    return [n["title"] for n in client.get("/api/orgs/demo/notifications", headers=headers).json()["items"]]


def test_coordinator_posts_to_a_year_of_their_department(client):
    cse = login(client, "cse.coordinator@demo.timetabl.ai")
    r = client.post("/api/orgs/demo/notices", headers=cse, json={
        "title": "3rd year: project review on Friday", "body": "Bring your report.", "kind": "year", "year": 3,
        "expires": _in(3)})
    assert r.status_code == 201, r.text
    assert r.json()["notice"]["for_whom"] == "CSE students, year 3"
    third, first = login(client, "cse3a.01@demo.timetabl.ai"), login(client, "cse1a.01@demo.timetabl.ai")
    assert "3rd year: project review on Friday" in _titles(client, third)
    assert "Notice: 3rd year: project review on Friday" in _bell(client, third)
    assert "3rd year: project review on Friday" not in _titles(client, first)
    assert "3rd year: project review on Friday" not in _titles(client, login(client, "ece3a.01@demo.timetabl.ai"))
    # Another department, the whole college and teachers posting are refused.
    for body in ({"kind": "dept_students", "department_id": "ece"}, {"kind": "college"}):
        bad = client.post("/api/orgs/demo/notices", headers=cse, json={"title": "x", "expires": _in(1), **body})
        assert bad.status_code == 403, bad.text
    teacher = login(client, "harpreet.kaur@demo.timetabl.ai")
    assert client.post("/api/orgs/demo/notices", headers=teacher, json={
        "title": "x", "kind": "section", "section_id": "cse-3a", "expires": _in(1)}).status_code == 403


def test_admin_posts_to_teachers_and_everyone_and_deletes(client):
    admin = login(client, "admin@demo.timetabl.ai")
    r = client.post("/api/orgs/demo/notices", headers=admin, json={
        "title": "ECE staff meeting at 4", "kind": "dept_teachers", "department_id": "ece", "expires": _in(1)})
    assert r.status_code == 201, r.text
    ece_teacher, cse_teacher = login(client, "kavita.rao@demo.timetabl.ai"), login(client, "harpreet.kaur@demo.timetabl.ai")
    assert "ECE staff meeting at 4" in _titles(client, ece_teacher)
    assert "ECE staff meeting at 4" in _titles(client, login(client, "ece.coordinator@demo.timetabl.ai"))
    assert "ECE staff meeting at 4" not in _titles(client, cse_teacher)
    everyone = client.post("/api/orgs/demo/notices", headers=admin, json={
        "title": "College closed on Monday", "kind": "college", "expires": _in(5)}).json()["notice"]
    assert "College closed on Monday" in _titles(client, cse_teacher)
    assert "College closed on Monday" in _titles(client, login(client, "me1a.01@demo.timetabl.ai"))
    # Only the poster (or the Admin) removes a notice.
    assert client.delete(f"/api/orgs/demo/notices/{everyone['id']}", headers=cse_teacher).status_code == 404
    assert client.delete(f"/api/orgs/demo/notices/{everyone['id']}", headers=admin).status_code == 204
    assert "College closed on Monday" not in _titles(client, cse_teacher)
    past = client.post("/api/orgs/demo/notices", headers=admin, json={
        "title": "Old", "kind": "college", "expires": _in(-1)})
    assert past.status_code == 422


def test_other_colleges_see_nothing(client):
    r = client.post("/api/auth/signup", json={"name": "Meera Das", "email": "meera@noticecollege.edu",
                                               "password": "longenough", "college_name": "Notice Test College"})
    assert r.status_code == 201, r.text
    outsider = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/orgs/demo/notices", headers=outsider).status_code == 404
    org = r.json()["memberships"][0]["org_id"]
    assert client.get(f"/api/orgs/{org}/notices", headers=outsider).json() == []
