"""A small, fictional college for trying Timetabl.ai from scratch: one department (CSE), three sections, one Excel
file. It uploads with 0 errors and generates in seconds, even on a small machine.

Run ``python -m app.seed.sample [folder]`` to write Sample_CSE.xlsx (default docs/demo-data/Sample).
Student logins: ``<roll no>@sample.test``, first password = roll number.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.models.domain import (
    Allotment,
    Batch,
    College,
    Department,
    Kind,
    LunchRule,
    Period,
    Section,
    Shift,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    Venue,
    VenueType,
)
from app.seed.gndec import _with_read_me, READ_ME

NAME = "Sample Institute of Technology"
DOMAIN = "sample.test"
DAY = Shift(id="day", name="Day", periods=[Period(start=f"{h:02d}:00", end=f"{h + 1:02d}:00") for h in range(9, 17)],
            lunch=LunchRule(window_start="12:00", window_end="14:00"))  # 8 periods, 09:00-17:00

# (code, name, year, lectures per week, lab blocks per week)
SUBJECTS = [
    ("CS101", "Programming in C", 1, 3, 1), ("MA101", "Engineering Mathematics", 1, 4, 0),
    ("PH101", "Engineering Physics", 1, 3, 0), ("HS101", "English Communication", 1, 2, 0),
    ("CS201", "Data Structures", 2, 3, 1), ("CS202", "Database Systems", 2, 3, 1),
    ("CS203", "Discrete Mathematics", 2, 3, 0), ("CS204", "Digital Electronics", 2, 3, 0),
    ("CS301", "Operating Systems", 3, 3, 1), ("CS302", "Computer Networks", 3, 3, 1),
    ("CS303", "Software Engineering", 3, 3, 0), ("CS304", "Web Technologies", 3, 2, 1),
]
# Teacher -> the subjects they teach (first one = their class); the others are back-ups for leave cover.
TEACHERS = [
    ("Dr. Meera Kapoor", ["CS101", "CS201"]), ("Prof. Arjun Malik", ["MA101", "CS203"]),
    ("Dr. Kavya Nanda", ["PH101", "CS204"]), ("Ms. Ritika Sood", ["HS101", "CS303"]),
    ("Dr. Rahul Verma", ["CS201", "CS101", "CS301"]), ("Prof. Neha Bhalla", ["CS202", "CS304"]),
    ("Dr. Sameer Khanna", ["CS203", "MA101"]), ("Prof. Pooja Dhawan", ["CS204", "PH101"]),
    ("Dr. Vikas Arora", ["CS301", "CS302", "CS201"]), ("Prof. Ishita Rana", ["CS302", "CS202"]),
]
EXTRA = {"CS303": "Ms. Ritika Sood", "CS304": "Prof. Neha Bhalla"}  # second subject these two teach
FIRST = ["Aarav", "Diya", "Kabir", "Ananya", "Rohan", "Isha", "Vihaan", "Sana", "Arjun", "Meher", "Yash", "Tara",
         "Dev", "Riya", "Aditya", "Naina", "Karan", "Simran", "Aryan", "Pihu"]
LAST = ["Sharma", "Gill", "Bansal", "Kaur", "Mehta", "Arora", "Singh", "Chopra", "Malhotra", "Sethi", "Bedi", "Jain"]


def build_sample_college() -> College:
    venues = [Venue(id=f"lh-{i}", name=f"LH-{i}", type=VenueType.lecture, capacity=66, department_id="cse")
              for i in (1, 2, 3)]
    venues += [Venue(id=f"lab-{i}", name=f"Computer Lab-{i}", type=VenueType.lab, capacity=32, tags=["computers"],
                     department_id="cse") for i in (1, 2)]
    sections, students = [], []
    for year in (1, 2, 3):
        sid = f"cse-{year}a"
        sec = Section(id=sid, name=f"CSE-{year}A", department_id="cse", year=year, strength=60, shift_id="day",
                      batches=[Batch(id=f"{sid}-1", name="A1", strength=30), Batch(id=f"{sid}-2", name="A2", strength=30)])
        sections.append(sec)
        for i in range(60):
            roll = f"{27 - year}01{i + 1:03d}"  # 2601001 = admitted 2026 (1st year), CSE, roll 001
            g = len(students)
            students.append(Student(id=f"st-{roll}", roll_no=roll, name=f"{FIRST[g % len(FIRST)]} {LAST[(g * 7) % len(LAST)]}",
                                    email=f"{roll}@{DOMAIN}", section_id=sid, batch_id=sec.batches[0 if i < 30 else 1].id))
    subjects = [Subject(id=c.lower(), code=c, name=n, department_id="cse", year=y, lectures_per_week=lec,
                        labs_per_week=labs, lab_tag="computers" if labs else None) for c, n, y, lec, labs in SUBJECTS]
    teachers, can_teach, owner = [], [], {}
    for k, (name, subs) in enumerate(TEACHERS, start=1):
        tid = f"t{k}"
        teachers.append(Teacher(id=tid, name=name, department_id="cse", shift_ids=["day"], max_per_day=5))
        for pref, code in enumerate(subs, start=1):
            can_teach.append(TeacherSubject(teacher_id=tid, subject_id=code.lower(), preference=min(pref, 2)))
        owner.setdefault(subs[0], tid)
    for code, name in EXTRA.items():
        owner[code] = next(t.id for t in teachers if t.name == name)
    allotments = []
    for s in subjects:
        sec = next(x for x in sections if x.year == s.year)
        if s.lectures_per_week:
            allotments.append(Allotment(id=f"a{len(allotments) + 1}", subject_id=s.id, teacher_id=owner[s.code],
                                        kind=Kind.lecture, section_ids=[sec.id]))
        for b in sec.batches[: 2 if s.labs_per_week else 0]:
            allotments.append(Allotment(id=f"a{len(allotments) + 1}", subject_id=s.id, teacher_id=owner[s.code],
                                        kind=Kind.lab, section_ids=[sec.id], batch_id=b.id))
    return College(id="sample", name=NAME, days=["Mon", "Tue", "Wed", "Thu", "Fri"], lab_periods=2, shifts=[DAY],
                   departments=[Department(id="cse", name="Computer Science and Engineering", short="CSE")],
                   venues=venues, sections=sections, teachers=teachers, subjects=subjects, allotments=allotments,
                   students=students, teacher_subjects=can_teach)


def write_files(folder: Path) -> list[Path]:
    from app.io.excel import template  # late import: excel imports the domain models only

    folder.mkdir(parents=True, exist_ok=True)
    intro = [("Computer Science and Engineering (CSE): 3 sections, 180 students, 10 teachers, 12 subjects, 5 rooms.", True),
             ("One file is the whole college: upload it on the CSE department page.", False), ("", False)]
    path = folder / "Sample_CSE.xlsx"
    path.write_bytes(_with_read_me(template(build_sample_college(), "cse"), f"{NAME} (sample): CSE", intro + READ_ME))
    return [path]


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "docs" / "demo-data" / "Sample"
    for p in write_files(target):
        print(p)
