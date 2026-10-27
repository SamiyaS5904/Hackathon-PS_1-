"""A second demo college re-engineered from Guru Nanak Dev Engineering College (GNDEC), Ludhiana.

What follows the real college (its public timetable, room and lab pages, 2026):
  * the time grid: Monday to Friday, nine 1-hour periods from 08:30 to 17:30, lunch around 11:30-13:30
    (here a flexible lunch: every section gets a free period between 11:30 and 13:30, every day)
  * section names (D1..D4 = year, CS / IT / ME / CE = branch, e.g. D3CS-B) and 2 lab groups per section
  * CSE / IT room and lab names (G-12.., S-213.., Software Lab-I..IV, DBMS, OS, PL, HW, WD, HPC labs),
    subjects per year, combined first-year classes taught by Applied Sciences
  * the JPAL hour in final-year CSE, which only some students attend (the others have a major-project
    review then), and a department elective in final year
What is made up: every person's name (teachers and students), roll numbers, the exact number of sections
(scaled down to 28 so the timetable solves in about a minute on a small laptop), ME / Civil lab names
(standard names; their pages could not be read) and who teaches what.

Logins (password DEMO_PASSWORD, like the demo college): admin@gndec.demo, <dept>.coordinator@gndec.demo,
teachers by name (e.g. harleen.grewal@gndec.demo) and students by roll number (e.g. 2315001@gndec.demo).
``demo_logins()`` lists a few of each for the Demo page. Nothing here writes to a database.

Run ``python -m app.seed.gndec <folder>`` to write the department Excel files and the blank template.
"""

from __future__ import annotations

import io
import itertools
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font

from app.models.domain import (
    Allotment,
    Batch,
    College,
    Department,
    DepartmentStatus,
    ElectiveGroup,
    ElectiveSlot,
    Holiday,
    Kind,
    LunchRule,
    Period,
    Rule,
    Section,
    Shift,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    Venue,
    VenueType,
)

ORG_ID = "gndec"
DOMAIN = "gndec.demo"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

DAY = Shift(
    id="day", name="Day",
    periods=[Period(start=f"{h:02d}:30", end=f"{h + 1:02d}:30") for h in range(8, 17)],  # 08:30 .. 17:30
    lunch=LunchRule(window_start="11:30", window_end="13:30"),
)

DEPARTMENTS = [
    Department(id="cse", name="Computer Science and Engineering", short="CSE"),
    Department(id="it", name="Information Technology", short="IT"),
    Department(id="me", name="Mechanical Engineering", short="ME"),
    Department(id="ce", name="Civil Engineering", short="CE"),
    Department(id="as", name="Applied Sciences", short="AS"),
]
BRANCH = {"cse": "CS", "it": "IT", "me": "ME", "ce": "CE"}
ROLL_CODE = {"cse": "15", "it": "16", "me": "13", "ce": "11"}  # branch part of the roll number
ADMITTED = {1: "26", 2: "25", 3: "24", 4: "23"}  # 2026-27 session: 1st years joined in 2026

# Sections per (department, year): about a third to a half of the real numbers (CSE has 6 a year).
SECTION_COUNT = {
    "cse": {1: 2, 2: 3, 3: 3, 4: 3},
    "it": {1: 1, 2: 2, 3: 2, 4: 2},
    "me": {1: 1, 2: 2, 3: 1, 4: 1},
    "ce": {1: 1, 2: 2, 3: 1, 4: 1},
}
STRENGTH = 60  # two lab groups of 30

L, P = Kind.lecture, Kind.lab


def _venues() -> list[Venue]:
    def lec(vid, name, seats, dept):
        return Venue(id=vid, name=name, type=VenueType.lecture, capacity=seats, department_id=dept)

    def lab(vid, name, seats, dept, *tags):
        return Venue(id=vid, name=name, type=VenueType.lab, capacity=seats, department_id=dept, tags=list(tags))

    return [
        # Shared hall for events (added by the College Admin in Setup; no class needs it)
        Venue(id="ws-hall", name="WS Seminar Hall", type=VenueType.seminar, capacity=200),
        # Applied Sciences: first-year rooms, halls and labs (in its Excel file, so uploads bring them along)
        lec("lt-1", "Lecture Theatre LT-1", 150, "as"),
        lec("lt-2", "Lecture Theatre LT-2", 130, "as"),
        Venue(id="dept-lib", name="CSE Department Library", type=VenueType.seminar, capacity=40, department_id="cse"),
        lec("a-101", "A-101", 70, "as"), lec("a-102", "A-102", 70, "as"),
        lab("phy-lab", "Physics Lab", 32, "as", "physics"),
        lab("ee-lab", "Basic Electrical Lab", 32, "as", "electrical"),
        lab("draw-1", "Drawing Hall-1", 32, "as", "drawing"), lab("draw-2", "Drawing Hall-2", 32, "as", "drawing"),
        lab("ws-1", "Central Workshop-1", 32, "as", "workshop"), lab("ws-2", "Central Workshop-2", 32, "as", "workshop"),
        # CSE (real rooms seat 75)
        lec("g-12", "G-12", 75, "cse"), lec("g-13", "G-13", 75, "cse"), lec("g-14", "G-14", 75, "cse"),
        lec("g-17", "G-17", 75, "cse"), lec("g-18", "G-18", 75, "cse"), lec("s-215", "S-215", 75, "cse"),
        lab("sl-1", "Software Lab-I", 35, "cse", "computers"), lab("sl-2", "Software Lab-II", 34, "cse", "computers"),
        lab("sl-3", "Software Lab-III", 35, "cse", "computers"), lab("sl-4", "Software Lab-IV", 30, "cse", "computers"),
        lab("dbms-lab", "DBMS Lab", 32, "cse", "computers"),
        lab("cse-pl", "Project Lab", 35, "cse", "computers", "project"),
        lab("cse-hw", "Hardware Lab", 30, "cse", "hardware"),
        Venue(id="jpal", name="JPAL Lab", type=VenueType.seminar, capacity=34, department_id="cse"),
        # IT
        lec("s-202", "S-202", 70, "it"), lec("s-203", "S-203", 70, "it"), lec("s-213", "S-213", 70, "it"),
        lab("it-pl", "PL Lab", 30, "it", "computers"), lab("it-os", "OS Lab", 30, "it", "computers"),
        lab("it-dbms", "IT DBMS Lab", 30, "it", "computers"), lab("it-wd", "WD Lab", 30, "it", "computers"),
        lab("it-hpc", "HPC Lab", 30, "it", "computers", "hpc"), lab("it-hw", "HW Lab (IT)", 30, "it", "hardware"),
        # Mechanical
        lec("m-101", "M-101", 70, "me"), lec("m-102", "M-102", 70, "me"),
        lab("som-lab", "Strength of Materials Lab", 32, "me", "som"),
        lab("tom-lab", "Theory of Machines Lab", 32, "me", "tom"),
        lab("thermal-lab", "Thermal Engineering Lab", 32, "me", "thermal"),
        lab("fm-lab", "Fluid Mechanics Lab", 32, "me", "fluids"),
        lab("cad-lab", "CAD/CAM Lab", 32, "me", "cad"),
        lab("machine-shop", "Machine Shop", 32, "me", "machining"),
        # Civil
        lec("c-101", "C-101", 70, "ce"), lec("c-102", "C-102", 70, "ce"),
        lab("survey-lab", "Surveying Lab", 32, "ce", "survey"),
        lab("concrete-lab", "Concrete Technology Lab", 32, "ce", "concrete"),
        lab("geotech-lab", "Geotechnical Lab", 32, "ce", "geotech"),
        lab("transport-lab", "Transportation Lab", 32, "ce", "transport"),
        lab("env-lab", "Environmental Engineering Lab", 32, "ce", "environment"),
        lab("civil-cad", "Civil CAD Lab", 32, "ce", "civil-cad"),
    ]


# First-year common subjects: all taught by Applied Sciences (first-year teaching), so its Excel file can be
# uploaded first and every branch's file names them. (code, name, department, lectures, lab blocks, equipment)
COMMON_FIRST_YEAR = [
    ("AM101", "Engineering Mathematics-I", "as", 4, 0, None),
    ("AP101", "Engineering Physics", "as", 3, 1, "physics"),
    ("EE101", "Basic Electrical Engineering", "as", 3, 1, "electrical"),
    ("HU101", "English Communication", "as", 2, 0, None),
    ("CS101", "Programming for Problem Solving", "as", 3, 1, "computers"),
    ("ME101", "Engineering Graphics and Design", "as", 1, 2, "drawing"),
    ("ME102", "Manufacturing Practice (Workshop)", "as", 0, 1, "workshop"),
]
SUBJECTS = {
    ("cse", 2): [("CS201", "Data Structures", 3, 1, "computers"), ("CS202", "Object Oriented Programming", 3, 1,
                 "computers"), ("CS203", "Digital Electronics", 3, 1, "hardware"),
                 ("CS204", "Computer Architecture", 3, 0, None)],
    ("cse", 3): [("CS301", "Design and Analysis of Algorithms", 3, 1, "computers"),
                 ("CS302", "Theory of Computation", 3, 0, None), ("CS303", "Software Engineering", 3, 1, "computers"),
                 ("CS304", "Cyber Security", 3, 1, "computers"), ("CS305", "Enterprise Resource Planning", 2, 0, None)],
    ("cse", 4): [("CS401", "Soft Computing", 3, 1, "computers"), ("CS402", "Web Technologies", 2, 1, "computers"),
                 ("CS403", "Major Project", 0, 1, "project")],
    ("it", 2): [("IT201", "Data Structures", 3, 1, "computers"),
                ("IT202", "Data Communication and Computer Networks", 3, 1, "computers"),
                ("IT203", "Digital Circuits and Logic Design", 3, 1, "hardware"),
                ("IT204", "Object Oriented Programming", 2, 1, "computers")],
    ("it", 3): [("IT301", "Database Management Systems", 3, 1, "computers"), ("IT302", "Operating Systems", 3, 1,
                 "computers"), ("IT303", "Web Development", 2, 1, "computers"),
                ("IT304", "Software Engineering", 3, 0, None), ("IT305", "Artificial Intelligence", 3, 0, None)],
    ("it", 4): [("IT401", "Machine Learning", 3, 1, "computers"), ("IT402", "Cloud Computing", 3, 1, "hpc"),
                ("IT403", "Information Security", 3, 0, None), ("IT404", "Major Project", 0, 1, "computers")],
    ("me", 2): [("ME201", "Strength of Materials", 3, 1, "som"), ("ME202", "Engineering Thermodynamics", 3, 0, None),
                ("ME203", "Theory of Machines", 3, 1, "tom"), ("ME204", "Manufacturing Processes", 3, 1, "machining")],
    ("me", 3): [("ME301", "Heat Transfer", 3, 1, "thermal"), ("ME302", "Fluid Mechanics", 3, 1, "fluids"),
                ("ME303", "Design of Machine Elements", 3, 0, None), ("ME304", "IC Engines", 3, 1, "thermal"),
                ("ME305", "Industrial Engineering", 2, 0, None)],
    ("me", 4): [("ME401", "Refrigeration and Air Conditioning", 3, 1, "thermal"), ("ME402", "CAD/CAM", 2, 1, "cad"),
                ("ME403", "Automobile Engineering", 3, 0, None), ("ME404", "Major Project", 0, 1, "cad")],
    ("ce", 2): [("CE201", "Surveying", 3, 1, "survey"), ("CE202", "Mechanics of Solids", 3, 1, "som"),
                ("CE203", "Fluid Mechanics", 3, 1, "fluids"), ("CE204", "Building Materials and Construction", 3, 0,
                                                                None)],
    ("ce", 3): [("CE301", "Structural Analysis", 3, 0, None), ("CE302", "Geotechnical Engineering", 3, 1, "geotech"),
                ("CE303", "Concrete Technology", 3, 1, "concrete"),
                ("CE304", "Transportation Engineering", 3, 1, "transport"), ("CE305", "Hydrology", 2, 0, None)],
    ("ce", 4): [("CE401", "Design of Steel Structures", 3, 0, None),
                ("CE402", "Environmental Engineering", 3, 1, "environment"),
                ("CE403", "Estimation and Costing", 3, 0, None), ("CE404", "Major Project", 0, 1, "civil-cad")],
}
APPLIED_MATHS = ("AM201", "Applied Mathematics", "as", 3)  # every 2nd-year section

# Made-up names (none taken from GNDEC's staff pages).
TEACHER_FIRST = ["Harleen", "Gurdeep", "Navneet", "Amandeep", "Rupinder", "Parminder", "Simranjit", "Kulwinder",
                 "Baljit", "Ravneet", "Sukhpreet", "Jagmeet", "Tejinder", "Manveer", "Inderpreet", "Daljeet",
                 "Charanjit", "Prabhjot", "Ishpreet", "Gagandeep", "Rajvir", "Komal", "Anupam", "Vikas", "Nitin",
                 "Pooja", "Ritika", "Sanjeev", "Meenu", "Deepika", "Rohit", "Shivani", "Aman", "Nidhi", "Varun",
                 "Ekta", "Sachin", "Tanvi", "Ankush", "Bhavna"]
TEACHER_LAST = ["Grewal", "Sidhu", "Bains", "Cheema", "Dhaliwal", "Randhawa", "Sekhon", "Bajwa", "Toor", "Brar",
                "Mann", "Gill", "Virk", "Sandhu", "Ahluwalia", "Bedi", "Chopra", "Khanna", "Malhotra", "Sood",
                "Bhalla", "Kohli", "Anand", "Sethi", "Walia", "Goyal", "Mittal", "Bansal", "Jindal", "Garg"]
STUDENT_FIRST = ["Aarav", "Ananya", "Arjun", "Diya", "Harleen", "Ishaan", "Jasleen", "Kabir", "Kavya", "Manav",
                 "Meher", "Navjot", "Nikita", "Pranav", "Priya", "Rahul", "Riya", "Sahil", "Sanya", "Simran",
                 "Tanvi", "Uday", "Vansh", "Zoya", "Aditi", "Gurleen", "Karan", "Muskan", "Rohan", "Sneha",
                 "Arshdeep", "Ekamjot", "Jashan", "Mehakpreet", "Noor", "Sehaj", "Taranpreet", "Yuvraj", "Avneet",
                 "Fatehbir", "Gurnoor", "Hargun", "Japneet", "Khushi", "Lovepreet", "Manjot", "Prabhleen",
                 "Rajbir", "Sukhmani", "Vihaan"]
STUDENT_LAST = ["Sharma", "Gill", "Verma", "Singh", "Kaur", "Gupta", "Arora", "Mehta", "Bansal", "Sandhu",
                "Dhillon", "Grewal", "Sidhu", "Kapoor", "Bedi", "Chawla", "Saini", "Thind", "Aulakh", "Jain",
                "Goyal", "Rana", "Bhatia", "Malhi", "Pannu"]

TITLES = ["Dr.", "Prof."]


def _teacher_names():
    """Unique made-up teacher names, in a mixed order."""
    pairs = list(itertools.product(TEACHER_FIRST, TEACHER_LAST))
    step = 37  # coprime with the number of pairs: walks through them in a scattered order
    for i in range(len(pairs)):
        first, last = pairs[(i * step) % len(pairs)]
        yield f"{TITLES[i % 2]} {first} {last}"


def build_gndec_college() -> College:
    venues = _venues()
    sections: list[Section] = []
    students: list[Student] = []
    for dept, years in SECTION_COUNT.items():
        for year, n in years.items():
            serial = 1
            for k in range(n):
                letter = "ABCDEF"[k]
                sid = f"d{year}{BRANCH[dept].lower()}-{letter.lower()}"
                strength = STRENGTH - (k % 2) * 2  # 60, 58, 60: real sections differ a little
                half = strength // 2
                sec = Section(id=sid, name=f"D{year}{BRANCH[dept]}-{letter}", department_id=dept, year=year,
                              strength=strength, shift_id="day",
                              batches=[Batch(id=f"{sid}-1", name=f"{letter}1", strength=half),
                                       Batch(id=f"{sid}-2", name=f"{letter}2", strength=strength - half)])
                sections.append(sec)
                for i in range(strength):
                    roll = f"{ADMITTED[year]}{ROLL_CODE[dept]}{serial:03d}"
                    g = len(students)  # running number over the whole college: names vary between sections
                    name = (f"{STUDENT_FIRST[(g * 7 + g // 50) % len(STUDENT_FIRST)]} "
                            f"{STUDENT_LAST[(g * 11 + g // 25) % len(STUDENT_LAST)]}")
                    students.append(Student(id=f"st-{roll}", roll_no=roll, name=name, email=f"{roll}@{DOMAIN}",
                                            section_id=sid, batch_id=sec.batches[0 if i < half else 1].id))
                    serial += 1

    subjects: list[Subject] = []
    for code, name, dept, lec, labs, tag in COMMON_FIRST_YEAR:
        subjects.append(Subject(id=code.lower(), code=code, name=name, department_id=dept, year=1,
                                lectures_per_week=lec, labs_per_week=labs, lab_tag=tag))
    code, name, dept, lec = APPLIED_MATHS
    subjects.append(Subject(id=code.lower(), code=code, name=name, department_id=dept, year=2, lectures_per_week=lec))
    for (dept, year), rows in SUBJECTS.items():
        for code, name, lec, labs, tag in rows:
            subjects.append(Subject(id=code.lower(), code=code, name=name, department_id=dept, year=year,
                                    lectures_per_week=lec, labs_per_week=labs, lab_tag=tag))
    subj = {s.id: s for s in subjects}

    # What each section takes: (subject id, sections taught together). First-year maths is a combined class.
    def secs(dept: str, year: int) -> list[Section]:
        return [s for s in sections if s.department_id == dept and s.year == year]

    classes: list[tuple[str, list[Section]]] = []
    d1 = [s for s in sections if s.year == 1]
    # CSE's two first-year sections share maths in a lecture theatre (a combined class stays inside one
    # department, so it also fits that department's Excel file).
    for p in [secs("cse", 1), secs("it", 1), secs("me", 1), secs("ce", 1)]:
        classes.append(("am101", p))
    for code, *_ in COMMON_FIRST_YEAR[1:]:
        classes += [(code.lower(), [s]) for s in d1]
    classes += [("am201", [s]) for s in sections if s.year == 2]
    for (dept, year), rows in SUBJECTS.items():
        for code, *_ in rows:
            classes += [(code.lower(), [s]) for s in secs(dept, year)]

    # Teachers: each subject's sections are shared out two at a time, so most subjects have 2+ teachers
    # (that is what the leave cover plan needs); a teacher keeps to one subject and at most ~16 periods a week.
    names = _teacher_names()
    teachers: list[Teacher] = []
    allotments: list[Allotment] = []
    teach: dict[str, list[str]] = {}  # subject id -> teacher ids (in order)

    def periods(subject: Subject, n_sections: int, combined: bool) -> int:
        lectures = subject.lectures_per_week * (1 if combined else n_sections)
        return lectures + subject.labs_per_week * 2 * 2 * n_sections  # 2 lab groups x 2-period blocks

    for sid in dict.fromkeys(c for c, _ in classes):
        s = subj[sid]
        groups = [g for c, g in classes if c == sid]
        chunk: list[list[Section]] = []
        for g in groups:
            if chunk and sum(len(x) for x in chunk) + len(g) <= 2 and periods(s, sum(len(x) for x in chunk) + len(g),
                                                                               len(g) > 1) <= 16:
                chunk.append(g)
                continue
            if chunk:
                _assign(s, chunk, teachers, allotments, teach, names)
            chunk = [g]
        _assign(s, chunk, teachers, allotments, teach, names)

    # Who can teach what: own subjects (1st choice), plus every subject of the department gets a second
    # teacher who could take it (2nd choice), so a teacher on leave can be covered by someone who knows it.
    teacher_subjects = [TeacherSubject(teacher_id=t, subject_id=s, preference=1)
                        for s, ts in teach.items() for t in dict.fromkeys(ts)]
    by_dept = {d.id: [t for t in teachers if t.department_id == d.id] for d in DEPARTMENTS}
    for s in subjects:
        own = set(teach.get(s.id, []))
        pool = [t for t in by_dept[s.department_id] if t.id not in own]
        same_year = [t for t in pool if any(subj[x].year == s.year for x, ts in teach.items() if t.id in ts)]
        for t in (same_year or pool)[:2 if len(own) < 2 else 1]:
            teacher_subjects.append(TeacherSubject(teacher_id=t.id, subject_id=s.id, preference=2))

    # Final-year CSE: a department elective (3 groups) and the JPAL hour (only some students).
    d4 = secs("cse", 4)
    d4_students = [st for st in students if st.section_id in {s.id for s in d4}]
    elective_names = [("cv", "CS411", "Computer Vision"), ("dwdm", "CS412", "Data Warehousing and Data Mining"),
                      ("sdn", "CS413", "Software Defined Networks")]
    groups = []
    for i, (gid, code, name) in enumerate(elective_names):
        subjects.append(Subject(id=code.lower(), code=code, name=name, department_id="cse", year=4,
                                lectures_per_week=0))
        tid = _new_teacher(teachers, names, "cse")
        teacher_subjects.append(TeacherSubject(teacher_id=tid, subject_id=code.lower(), preference=1))
        groups.append(ElectiveGroup(id=gid, name=name, subject_id=code.lower(), teacher_id=tid,
                                    student_ids=[st.id for k, st in enumerate(d4_students) if k % 3 == i]))
    dept_elective = ElectiveSlot(id="cse-d4-elective", name="Department Elective (D4 CSE)",
                                 section_ids=[s.id for s in d4], lectures_per_week=3, groups=groups)

    # JPAL: about 30 selected final-year CSE students (every 6th roll number, from the 4th); everyone else has a
    # major-project review with their own section's guide at that hour.
    jpal_ids = [st.id for k, st in enumerate(d4_students) if k % 6 == 3]
    subjects.append(Subject(id="cs420", code="CS420", name="JPAL", department_id="cse", year=4, lectures_per_week=0))
    subjects.append(Subject(id="cs421", code="CS421", name="Major Project Review", department_id="cse", year=4,
                            lectures_per_week=0))
    jpal_teacher = _new_teacher(teachers, names, "cse")
    teacher_subjects.append(TeacherSubject(teacher_id=jpal_teacher, subject_id="cs420", preference=1))
    jpal_groups = [ElectiveGroup(id="jpal", name="JPAL", subject_id="cs420", teacher_id=jpal_teacher,
                                 student_ids=jpal_ids)]
    project_guides = teach["cs403"]
    for k, sec in enumerate(d4):
        guide = project_guides[k % len(project_guides)] if k < len(project_guides) else _new_teacher(teachers, names,
                                                                                                    "cse")
        jpal_groups.append(ElectiveGroup(
            id=f"review-{sec.id}", name=f"Major Project Review ({sec.name})", subject_id="cs421", teacher_id=guide,
            student_ids=[st.id for st in d4_students if st.section_id == sec.id and st.id not in jpal_ids]))
    jpal = ElectiveSlot(id="cse-d4-jpal", name="JPAL hour (D4 CSE)", section_ids=[s.id for s in d4],
                        lectures_per_week=1, groups=jpal_groups)

    return College(
        id=ORG_ID, name="Guru Nanak Dev Engineering College (demo)", days=DAYS, lab_periods=2, shifts=[DAY],
        departments=DEPARTMENTS, venues=venues, sections=sections, teachers=teachers, subjects=subjects,
        allotments=allotments, students=students, elective_slots=[dept_elective, jpal],
        teacher_subjects=teacher_subjects,
        holidays=[Holiday(date="2026-11-24", label="Guru Nanak Dev Ji Gurpurab")],
        semester_start="2026-08-05", semester_end="2026-12-04",
        rules=[Rule(id="mess-split", name="Spread lunch evenly (mess split)", kind="spread_lunch", mode="try",
                    weight=4)],
        setup_saved=True,
        # A finished setup: every department has marked its data Ready (1 Aug 2026), so the Admin can generate.
        department_status={d.id: DepartmentStatus(ready=True, at=1785542400.0, by=f"{d.short} Coordinator")
                           for d in DEPARTMENTS},
    )


def _new_teacher(teachers: list[Teacher], names, dept: str) -> str:
    tid = f"g-t{len(teachers) + 1}"
    teachers.append(Teacher(id=tid, name=next(names), department_id=dept, shift_ids=["day"], max_per_day=5))
    return tid


def _assign(s: Subject, chunk: list[list[Section]], teachers, allotments, teach, names) -> None:
    tid = _new_teacher(teachers, names, s.department_id)
    teach.setdefault(s.id, []).append(tid)
    for group in chunk:
        ids = [x.id for x in group]
        if s.lectures_per_week:
            allotments.append(Allotment(id=f"g-a{len(allotments) + 1}", subject_id=s.id, teacher_id=tid,
                                        kind=L, section_ids=ids))
        if s.labs_per_week:
            for sec in group:
                for b in sec.batches:
                    allotments.append(Allotment(id=f"g-a{len(allotments) + 1}", subject_id=s.id, teacher_id=tid,
                                                kind=P, section_ids=[sec.id], batch_id=b.id))


def demo_logins(college: College) -> list[dict]:
    """A few ready-made logins for the Demo page: Admin, each Coordinator, two teachers per department and one
    student per section (all use DEMO_PASSWORD; app.accounts.seed_accounts creates them with ``DOMAIN``)."""
    from app.accounts import _slug_email  # same email rule as the account seeding

    out = [{"role": "admin", "name": "College Admin", "email": f"admin@{DOMAIN}"}]
    out += [{"role": "coordinator", "name": f"{d.short} Coordinator", "email": f"{d.id}.coordinator@{DOMAIN}"}
            for d in college.departments]
    used = {o["email"] for o in out}
    emails = {t.id: _slug_email(t.name, DOMAIN, used) for t in college.teachers}  # same order as seed_accounts
    for d in college.departments:
        for t in [t for t in college.teachers if t.department_id == d.id][:2]:
            out.append({"role": "teacher", "name": t.name, "email": emails[t.id], "department": d.short})
    jpal = {i for g in college.elective_slot("cse-d4-jpal").groups if g.id == "jpal" for i in g.student_ids}
    for sec in college.sections:
        st = next(x for x in college.students if x.section_id == sec.id)
        out.append({"role": "student", "name": st.name, "email": st.email, "section": sec.name})
    listed = {o["email"] for o in out}
    st = next(x for x in college.students if x.id in jpal and x.email not in listed)
    out.append({"role": "student", "name": st.name, "email": st.email, "section": "JPAL student"})
    return out


# ---- Excel files (the department upload format) -------------------------------------------------------

READ_ME = [
    ("Timetabl.ai: one department's data", True),
    ("", False),
    ("Fill one file per department and upload it on the department's page (Setup > Departments > Upload Excel).", False),
    ("Rows are checked before anything is saved; problems are shown row by row. A '*' marks a required column.", False),
    ("", False),
    ("Sections: one row per section (a group of students who always sit together).", True),
    ("  Section: its name, e.g. D2CS-A. Year: 1-4. Students: how many. Shift: the shift name from Setup (e.g. Day).", False),
    ("  Lab batches: how the section splits for labs, e.g. 'A1:30, A2:30' (name:students). Empty = whole section.", False),
    ("Teachers: one row per teacher of the department.", True),
    ("  Name, Email (their login), Shifts (one or more shift names, comma separated), Max periods per day (default 5).", False),
    ("Subjects: one row per subject the department teaches.", True),
    ("  Code, Name, Year, Lectures per week, Labs per week (lab blocks; one block = the college's lab length, e.g. 2 periods),", False),
    ("  Lab equipment: what the lab room must have, e.g. computers. It must match a lab room's Equipment.", False),
    ("Can teach: which subjects each teacher can teach. Preference 1 = first choice, 2 = could also teach it.", True),
    ("  Used for teacher suggestions and to find a substitute when a teacher is on leave.", False),
    ("Classes: one row per class. Subject code, Sections (several separated by commas = one combined class),", True),
    ("  Type (Lecture or Lab), Batch ('all' = one lab for each lab batch, or one batch name), Teacher (may be empty).", False),
    ("  A teacher or subject of another department (e.g. Applied Sciences for first-year maths) can be named too,", False),
    ("  once that department's file is uploaded: upload Applied Sciences first.", False),
    ("Students: Roll no, Name, Email (their login; first password = roll number), Section, Batch.", True),
    ("Rooms: rooms this department owns. Type: Lecture, Lab or Seminar. Seats. Equipment for labs.", True),
    ("  Rooms every department may use (e.g. a seminar hall) are added by the College Admin in Setup as shared rooms.", False),
    ("", False),
    ("Not in this file: the time grid, lunch window, holidays, electives and pooled groups (e.g. JPAL),", False),
    ("rules and shared rooms. The College Admin sets those in Setup.", False),
]


def _with_read_me(content: bytes, title: str, lines: list[tuple[str, bool]]) -> bytes:
    wb = load_workbook(io.BytesIO(content))
    ws = wb.create_sheet("Read me", 0)
    ws.column_dimensions["A"].width = 120
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14)
    for text, bold in lines:
        ws.append([text])
        if bold:
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    wb.active = 0
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def blank_template() -> bytes:
    """The department format with headings only (and the help notes), plus a Read me sheet."""
    from app.io.excel import template  # late import: excel imports the domain models only

    content = template(build_gndec_college().model_copy(update={"sections": []}), "none")
    wb = load_workbook(io.BytesIO(content))
    for ws in wb.worksheets:
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)
    buf = io.BytesIO()
    wb.save(buf)
    return _with_read_me(buf.getvalue(), "Timetabl.ai: blank department template", READ_ME)


def department_files(college: College | None = None) -> dict[str, bytes]:
    """One upload file per department, filled with this college's data (Applied Sciences first)."""

    college = college or build_gndec_college()
    out = {}
    for i, dept in enumerate(["as", "cse", "it", "me", "ce"], start=1):
        d = next(x for x in college.departments if x.id == dept)
        secs = sum(1 for s in college.sections if s.department_id == dept)
        studs = sum(1 for s in college.students if college.section(s.section_id).department_id == dept)
        tchs = sum(1 for t in college.teachers if t.department_id == dept)
        intro = [(f"{d.name} ({d.short}): {secs} sections, {studs} students, {tchs} teachers.", True),
                 ("Upload order: Applied Sciences first (its teachers teach first-year classes of every branch),", False),
                 ("then CSE, IT, ME and CE. Its file also has the lecture theatres, drawing halls and workshops of", False),
                 ("first year. Not in the files: the JPAL hour and the final-year CSE elective (they need a student list", False),
                 ("per group; they are in the built-in GNDEC demo college).", False), ("", False)]
        out[f"GNDEC_{i}_{d.short}.xlsx"] = _with_read_me(_dept_template(college, dept), f"GNDEC (demo): {d.name}",
                                                          intro + READ_ME)
    return out


def _dept_template(college: College, dept: str) -> bytes:
    """The filled template. A department without sections of its own (Applied Sciences) would get the
    template's example rows, so a placeholder section is added and its row removed again."""
    from app.io.excel import template

    if any(s.department_id == dept for s in college.sections):
        return template(college, dept)
    placeholder = Section(id="__placeholder", name="__placeholder", department_id=dept, year=1, strength=1,
                          shift_id=college.shifts[0].id)
    wb = load_workbook(io.BytesIO(template(college.model_copy(update={"sections": [*college.sections, placeholder]}),
                                           dept)))
    ws = wb["Sections"]
    for row in range(ws.max_row, 1, -1):
        if ws.cell(row=row, column=1).value == "__placeholder":
            ws.delete_rows(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def write_files(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    files = {"Timetabl_blank_template.xlsx": blank_template(), **department_files()}
    for name, content in files.items():
        (folder / name).write_bytes(content)
        written.append(folder / name)
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "docs" / "demo-data" / "GNDEC"
    for p in write_files(target):
        print(p)
