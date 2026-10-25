"""Auto-sectioning: whole-year list -> balanced sections + lab batches, keeping ids on re-sectioning."""

import io

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app import sectioning
from app.main import app
from app.seed.demo_college import build_demo_college
from app.solver import feasibility


def _sheet(rows, header=("Roll no", "Name", "Email", "Hostel")) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _year(n, hostel_every=4, prefix="R"):
    return [(f"{prefix}{i}", f"Student {i}", f"s{i}@x.edu", "Day scholar" if i % hostel_every == 0 else "Hosteller")
            for i in range(1, n + 1)]


def test_split_by_roll_is_balanced_and_in_natural_order():
    rows, errors, cols = sectioning.parse(_sheet(_year(125)))
    assert errors == [] and cols == ["Hostel"]
    groups = sectioning.split(rows, 60, None)
    assert [len(g) for g in groups] == [42, 42, 41]
    assert groups[0][0].roll_no == "R1" and groups[0][1].roll_no == "R2" and groups[0][9].roll_no == "R10"
    assert groups[1][0].roll_no == "R43"  # consecutive roll numbers stay together


def test_mixing_gives_every_section_a_fair_share():
    rows, _, _ = sectioning.parse(_sheet(_year(120)))  # 90 hostellers, 30 day scholars
    groups = sectioning.split(rows, 60, "Hostel")
    assert [len(g) for g in groups] == [60, 60]
    for g in groups:
        assert sum(r.extra["Hostel"] == "Day scholar" for r in g) == 15
        assert [r.roll_no for r in g] == sorted((r.roll_no for r in g), key=sectioning._natural)


def test_row_errors_name_the_row():
    rows = _year(3) + [("R2", "Dup", "dup@x.edu", ""), ("R9", "Bad", "not-an-email", ""), ("", "No roll", "a@x.edu", "")]
    _, errors, _ = sectioning.parse(_sheet(rows))
    msgs = {e.row: e.message for e in errors}
    assert "also on row 3" in msgs[5] and "valid email" in msgs[6] and "all needed" in msgs[7]
    _, errors, _ = sectioning.parse(_sheet(_year(2), header=("Roll", "Name", "Email", "Hostel")))
    assert "Missing column" in errors[0].message
    assert "isn't an Excel" in sectioning.parse(b"hello")[1][0].message


def test_resectioning_keeps_section_and_student_ids():
    c = build_demo_college()
    before = {s.name: s.id for s in c.sections if s.department_id == "cse" and s.year == 1}
    rows, _, _ = sectioning.parse(_sheet(_year(130)))
    p, _ = sectioning.plan(c, "cse", 1, rows, 65, 2, None, None)
    assert [s.batches for s in p.sections] == [[33, 32], [33, 32]]
    assert any("Lab groups of 33" in w for w in p.warnings)  # labs seat 32: warned before saving
    rows, _, _ = sectioning.parse(_sheet(_year(128)))
    p, groups = sectioning.plan(c, "cse", 1, rows, 64, 2, None, None)
    assert [s.name for s in p.sections] == ["CSE-1A", "CSE-1B"] and p.replaces == ["CSE-1A", "CSE-1B"]
    assert p.warnings == []
    new, problems = sectioning.apply(c, "cse", p, groups, actor="test")
    assert problems == [] and new is not None
    after = {s.name: s.id for s in new.sections if s.department_id == "cse" and s.year == 1}
    assert after == before  # classes stay linked
    year1 = [st for st in new.students if st.section_id in after.values()]
    assert len(year1) == 128 and all(st.batch_id for st in year1)
    assert feasibility.check(new) == []  # still ready to generate
    # Students of other years are untouched.
    assert len([st for st in new.students if st.section_id == "cse-2a"]) == \
        len([st for st in c.students if st.section_id == "cse-2a"])


def test_a_section_with_classes_cant_disappear():
    c = build_demo_college()
    rows, _, _ = sectioning.parse(_sheet(_year(100)))
    p, groups = sectioning.plan(c, "cse", 1, rows, 120, 2, None, None)  # one big section
    new, problems = sectioning.apply(c, "cse", p, groups, actor="test")
    assert new is None and any("CSE-1B would disappear" in x for x in problems)
    assert any("No lecture room" in w or "shared rooms" in w for w in p.warnings) or p.sections[0].size <= 66


def test_api_preview_then_save():
    with TestClient(app) as client:
        h = {"Authorization": "Bearer " + client.post(
            "/api/auth/login", json={"email": "cse.coordinator@demo.timetabl.ai", "password": "demo1234"}).json()["token"]}
        t = client.get("/api/orgs/demo/departments/cse/year-list-template", headers=h)
        assert t.status_code == 200 and t.content[:2] == b"PK"
        assert client.get("/api/orgs/demo/departments/ece/year-list-template", headers=h).status_code == 403
        files = {"file": ("year.xlsx", _sheet(_year(128, prefix="Y4-")), "application/octet-stream")}
        url = "/api/orgs/demo/departments/cse/auto-sections?year=4&max_size=64&batches=2&mix_by=Hostel"
        preview = client.post(url, headers=h, files=files).json()
        assert preview["errors"] == [] and not preview["saved"] and preview["problems"] == []
        assert [s["name"] for s in preview["plan"]["sections"]] == ["CSE-4A", "CSE-4B"]
        assert preview["plan"]["sections"][0]["mix"] == {"Day scholar": 16, "Hosteller": 48}
        saved = client.post(url + "&commit=true", headers=h, files=files).json()
        assert saved["saved"]
        college = client.get("/api/orgs/demo/college", headers=h).json()
        assert {"CSE-4A", "CSE-4B"} <= {s["name"] for s in college["sections"]}
