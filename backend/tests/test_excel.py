"""Excel template + import: round trip, row-level errors, preview vs save."""

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.college_edit import dept_slice, merge_dept
from app.io.excel import parse, template
from app.main import app
from app.seed.demo_college import build_demo_college
from app.solver import feasibility


def _edit(content: bytes, sheet: str, rows: list[list]) -> bytes:
    wb = load_workbook(io.BytesIO(content))
    ws = wb[sheet]
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_round_trip_keeps_department_data_and_ids():
    c = build_demo_college()
    before = dept_slice(c, "cse")
    result = parse(c, "cse", template(c, "cse"))
    assert result.errors == [], result.errors[:3]
    d = result.data
    assert {s.id for s in d.sections} == {s.id for s in before.sections}
    assert {t.id for t in d.teachers} == {t.id for t in before.teachers}
    assert {s.id for s in d.subjects} == {s.id for s in before.subjects}
    assert len(d.allotments) == len(before.allotments)
    assert len(d.students) == len(before.students) == 360
    assert {(a.subject_id, tuple(a.section_ids), a.batch_id, a.teacher_id) for a in d.allotments} == \
           {(a.subject_id, tuple(a.section_ids), a.batch_id, a.teacher_id) for a in before.allotments}
    assert {s.id for s in d.students} == {s.id for s in before.students}  # elective groups refer to these
    merged, errs = merge_dept(c, "cse", d, actor="test")
    assert errs == [] and merged is not None
    assert feasibility.check(merged) == []  # the re-imported college is still ready to generate


def test_row_errors_name_the_sheet_and_row():
    c = build_demo_college()
    content = _edit(template(c, "cse"), "Classes", [["CS299", "CSE-2A", "Lecture", "", ""],
                                                     ["CS201", "CSE-9Z", "Lecture", "", ""],
                                                     ["CS201", "CSE-2A", "Seminar", "", ""]])
    content = _edit(content, "Sections", [["CSE-4A", 4, 60, "Evening", "B1:20, B2:20"]])
    content = _edit(content, "Students", [["X1", "X", "not-an-email", "CSE-2A", ""]])
    r = parse(c, "cse", content)
    assert r.data is None
    assert any(e.sheet == "Classes" and "CS299" in e.message for e in r.errors)
    assert any(e.sheet == "Classes" and "CSE-9Z" in e.message for e in r.errors)
    assert any(e.sheet == "Classes" and "Lecture or Lab" in e.message for e in r.errors)
    assert any(e.sheet == "Sections" and "add up to 40, not 60" in e.message for e in r.errors)
    assert any(e.sheet == "Students" and "valid email" in e.message for e in r.errors)
    assert all(e.row >= 2 for e in r.errors)


def test_not_an_excel_file():
    r = parse(build_demo_college(), "cse", b"hello")
    assert r.errors and "isn't an Excel" in r.errors[0].message


def test_api_template_preview_and_commit():
    with TestClient(app) as client:
        h = {"Authorization": "Bearer " + client.post(
            "/api/auth/login", json={"email": "cse.coordinator@demo.timetabl.ai", "password": "demo1234"}).json()["token"]}
        t = client.get("/api/orgs/demo/departments/cse/template", headers=h)
        assert t.status_code == 200 and t.headers["content-type"].startswith("application/vnd.openxml")
        assert client.get("/api/orgs/demo/departments/ece/template", headers=h).status_code == 403
        files = {"file": ("cse.xlsx", t.content, "application/octet-stream")}
        preview = client.post("/api/orgs/demo/departments/cse/import", headers=h, files=files).json()
        assert preview["errors"] == [] and preview["counts"]["sections"] == 6 and not preview["saved"]
        bad = _edit(t.content, "Classes", [["NOPE", "CSE-2A", "Lecture", "", ""]])
        out = client.post("/api/orgs/demo/departments/cse/import?commit=true", headers=h,
                          files={"file": ("cse.xlsx", bad, "application/octet-stream")}).json()
        assert out["errors"] and not out["saved"]  # errors: nothing saved
        out = client.post("/api/orgs/demo/departments/cse/import?commit=true", headers=h, files=files).json()
        assert out["saved"] and out["errors"] == []
