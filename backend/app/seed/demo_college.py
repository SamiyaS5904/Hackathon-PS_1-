"""A realistic demo college used for development, tests and the hackathon demo.

Deliberately exercises the hard cases:
  * 2 shifts that overlap in time (Morning: 1st years, Evening: 2nd & 3rd years)
    and share venues and some teachers
  * staggered lunch per year inside the Evening shift
  * combined classes (Engineering Maths for two sections in one big hall)
  * labs as 2-period blocks, split into parallel batches
  * shared venues (Seminar Hall, Physics/Chemistry labs) and department-owned ones
  * a teacher who teaches in both shifts, and a teacher with a blocked time
"""

from __future__ import annotations

from app.models.domain import (
    Allotment,
    Batch,
    College,
    Department,
    ElectiveGroup,
    ElectiveSlot,
    Kind,
    LunchRule,
    Period,
    Section,
    Shift,
    Student,
    Subject,
    Teacher,
    TeacherSubject,
    TimeBlock,
    Venue,
    VenueType,
)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

MORNING = Shift(
    id="morning",
    name="Morning",
    periods=[
        Period(start="08:30", end="09:20"),
        Period(start="09:20", end="10:10"),
        Period(start="10:10", end="11:00"),
        Period(start="11:00", end="11:50"),
        # lunch 11:50-12:30
        Period(start="12:30", end="13:20"),
        Period(start="13:20", end="14:10"),
        Period(start="14:10", end="15:00"),
    ],
)

EVENING = Shift(
    id="evening",
    name="Evening",
    periods=[
        Period(start="11:00", end="11:50"),
        Period(start="11:50", end="12:40"),
        Period(start="12:40", end="13:30"),
        Period(start="13:30", end="14:20"),
        # tea break 14:20-14:40
        Period(start="14:40", end="15:30"),
        Period(start="15:30", end="16:20"),
        Period(start="16:20", end="17:10"),
    ],
    # Mess serves 12:40-14:20; the solver picks each year's lunch period inside it.
    lunch=LunchRule(window_start="12:40", window_end="14:20"),
)

DEPARTMENTS = [
    Department(id="cse", name="Computer Science & Engineering", short="CSE"),
    Department(id="ece", name="Electronics & Communication", short="ECE"),
    Department(id="me", name="Mechanical Engineering", short="ME"),
    Department(id="as", name="Applied Sciences", short="AS"),
]

VENUES = [
    Venue(id="sem-hall", name="Seminar Hall", type=VenueType.seminar, capacity=150),
    Venue(id="lt-1", name="Lecture Theatre 1", type=VenueType.lecture, capacity=130),
    Venue(id="phy-lab", name="Physics Lab", type=VenueType.lab, capacity=32, tags=["physics"]),
    Venue(id="chem-lab", name="Chemistry Lab", type=VenueType.lab, capacity=32, tags=["chemistry"]),
    Venue(id="lh-101", name="LH-101", type=VenueType.lecture, capacity=66, department_id="cse"),
    Venue(id="lh-102", name="LH-102", type=VenueType.lecture, capacity=66, department_id="cse"),
    Venue(id="lh-103", name="LH-103", type=VenueType.lecture, capacity=66, department_id="cse"),
    Venue(id="cse-lab-1", name="CSE Lab 1", type=VenueType.lab, capacity=32, tags=["computers"], department_id="cse"),
    Venue(id="cse-lab-2", name="CSE Lab 2", type=VenueType.lab, capacity=32, tags=["computers"], department_id="cse"),
    Venue(id="lh-201", name="LH-201", type=VenueType.lecture, capacity=66, department_id="ece"),
    Venue(id="lh-202", name="LH-202", type=VenueType.lecture, capacity=66, department_id="ece"),
    Venue(id="ece-lab", name="Electronics Lab", type=VenueType.lab, capacity=32, tags=["electronics"], department_id="ece"),
    Venue(id="lh-301", name="LH-301", type=VenueType.lecture, capacity=66, department_id="me"),
    Venue(id="lh-302", name="LH-302", type=VenueType.lecture, capacity=66, department_id="me"),
    Venue(id="me-shop", name="ME Workshop", type=VenueType.lab, capacity=32, tags=["mechanical"], department_id="me"),
]


def _section(dept: str, year: int, letter: str, shift: str, strength: int = 60) -> Section:
    sid = f"{dept}-{year}{letter.lower()}"
    half = strength // 2
    return Section(
        id=sid,
        name=f"{dept.upper()}-{year}{letter}",
        department_id=dept,
        year=year,
        strength=strength,
        shift_id=shift,
        batches=[
            Batch(id=f"{sid}-b1", name="B1", strength=half),
            Batch(id=f"{sid}-b2", name="B2", strength=strength - half),
        ],
    )


SECTIONS = [
    _section("cse", 1, "A", "morning"),
    _section("cse", 1, "B", "morning"),
    _section("ece", 1, "A", "morning"),
    _section("me", 1, "A", "morning"),
    _section("cse", 2, "A", "evening"),
    _section("cse", 2, "B", "evening"),
    _section("ece", 2, "A", "evening"),
    _section("me", 2, "A", "evening"),
    _section("cse", 3, "A", "evening"),
    _section("cse", 3, "B", "evening"),
    _section("ece", 3, "A", "evening"),
    _section("me", 3, "A", "evening"),
]

# (code, name, lectures/week, labs/week, lab tag)
UPPER_YEAR_SUBJECTS = {
    ("cse", 2): [
        ("CS201", "Data Structures", 3, 1, "computers"),
        ("CS202", "Database Systems", 3, 1, "computers"),
        ("CS203", "Operating Systems", 3, 0, None),
        ("CS204", "Discrete Mathematics", 3, 0, None),
        ("CS205", "Computer Organisation", 3, 0, None),
    ],
    ("cse", 3): [
        ("CS301", "Computer Networks", 3, 1, "computers"),
        ("CS302", "Machine Learning", 3, 1, "computers"),
        ("CS303", "Software Engineering", 3, 0, None),
        ("CS304", "Theory of Computation", 3, 0, None),
        ("CS305", "Compiler Design", 3, 0, None),
    ],
    ("ece", 2): [
        ("EC201", "Analog Circuits", 3, 1, "electronics"),
        ("EC202", "Digital Electronics", 3, 1, "electronics"),
        ("EC203", "Signals & Systems", 3, 0, None),
        ("EC204", "Network Theory", 3, 0, None),
        ("EC205", "Electromagnetics", 3, 0, None),
    ],
    ("ece", 3): [
        ("EC301", "Microprocessors", 3, 1, "electronics"),
        ("EC302", "Communication Systems", 3, 1, "electronics"),
        ("EC303", "Control Systems", 3, 0, None),
        ("EC304", "VLSI Design", 3, 0, None),
        ("EC305", "Antennas", 3, 0, None),
    ],
    ("me", 2): [
        ("ME201", "Thermodynamics", 3, 1, "mechanical"),
        ("ME202", "Manufacturing Processes", 3, 1, "mechanical"),
        ("ME203", "Strength of Materials", 3, 0, None),
        ("ME204", "Fluid Mechanics", 3, 0, None),
        ("ME205", "Kinematics", 3, 0, None),
    ],
    ("me", 3): [
        ("ME301", "Heat Transfer", 3, 1, "mechanical"),
        ("ME302", "Machine Design", 3, 1, "mechanical"),
        ("ME303", "Dynamics of Machines", 3, 0, None),
        ("ME304", "IC Engines", 3, 0, None),
        ("ME305", "Industrial Engineering", 3, 0, None),
    ],
}

FIRST_YEAR_SUBJECTS = [
    ("MA101", "Engineering Maths", 4, 0, None),
    ("PH101", "Physics", 3, 1, "physics"),
    ("CY101", "Chemistry", 3, 1, "chemistry"),
    ("CS101", "Programming in C", 3, 1, "computers"),
    ("ME101", "Engineering Graphics", 3, 0, None),
]

TEACHER_NAMES = [
    "Dr. Harpreet Kaur", "Prof. Rohit Bansal", "Dr. Neha Arora", "Prof. Amit Malhotra",
    "Dr. Simran Gill", "Prof. Karan Mehra", "Dr. Priya Nair", "Prof. Sandeep Joshi",
    "Dr. Ritu Saini", "Prof. Manish Tiwari", "Dr. Kavita Rao", "Prof. Deepak Chauhan",
    "Dr. Jaspreet Sandhu", "Prof. Nikhil Kapoor", "Dr. Sunita Yadav", "Prof. Arjun Reddy",
    "Dr. Meenakshi Iyer", "Prof. Gaurav Sethi", "Dr. Anjali Bhatt", "Prof. Varun Khanna",
    "Dr. Shalini Dutta", "Prof. Mohit Aggarwal", "Dr. Rekha Pillai", "Prof. Tarun Grover",
    "Dr. Nidhi Chawla", "Prof. Ankit Saxena", "Dr. Pallavi Desai", "Prof. Sahil Dhillon",
    "Dr. Monika Bedi", "Prof. Yash Thakur",
]


def build_demo_college() -> College:
    subjects: list[Subject] = []
    teachers: list[Teacher] = []
    allotments: list[Allotment] = []
    names = iter(TEACHER_NAMES)

    def add_allotments(subj: Subject, teacher_id: str, section_groups: list[list[Section]]) -> None:
        for group in section_groups:
            if subj.lectures_per_week:
                allotments.append(
                    Allotment(
                        id=f"a{len(allotments) + 1}",
                        subject_id=subj.id,
                        teacher_id=teacher_id,
                        kind=Kind.lecture,
                        section_ids=[s.id for s in group],
                    )
                )
            if subj.labs_per_week:
                for sec in group:
                    for b in sec.batches:
                        allotments.append(
                            Allotment(
                                id=f"a{len(allotments) + 1}",
                                subject_id=subj.id,
                                teacher_id=teacher_id,
                                kind=Kind.lab,
                                section_ids=[sec.id],
                                batch_id=b.id,
                            )
                        )

    # Upper years: one teacher per subject, teaching every section of that dept-year.
    for (dept, year), rows in UPPER_YEAR_SUBJECTS.items():
        secs = [s for s in SECTIONS if s.department_id == dept and s.year == year]
        for code, name, lec, lab, tag in rows:
            subj = Subject(id=code.lower(), code=code, name=name, department_id=dept, year=year,
                           lectures_per_week=lec, labs_per_week=lab, lab_tag=tag)
            subjects.append(subj)
            tid = f"t{len(teachers) + 1}"
            teachers.append(Teacher(id=tid, name=next(names), department_id=dept, shift_ids=["evening"], max_per_day=5))
            add_allotments(subj, tid, [[s] for s in secs])

    # First year (Morning shift): common subjects, mostly Applied Sciences.
    fy = [s for s in SECTIONS if s.year == 1]
    pairs = [[fy[0], fy[1]], [fy[2], fy[3]]]  # CSE-1A+1B, ECE-1A+ME-1A
    first_year_teachers = {
        "MA101": [("t-anita", "Dr. Anita Sharma", "as")],
        "PH101": [("t-rajesh", "Dr. Rajesh Kumar", "as"), ("t-meena", "Dr. Meena Gupta", "as")],
        "CY101": [("t-pooja", "Dr. Pooja Verma", "as"), ("t-arun", "Dr. Arun Mehta", "as")],
        "CS101": [("t-vikram", "Prof. Vikram Singh", "cse"), ("t-raman", "Prof. Ramandeep Kaur", "cse")],
        "ME101": [("t-lakhwinder", "Prof. Lakhwinder Singh", "me")],
    }
    for code, name, lec, lab, tag in FIRST_YEAR_SUBJECTS:
        dept = {"CS101": "cse", "ME101": "me"}.get(code, "as")
        subj = Subject(id=code.lower(), code=code, name=name, department_id=dept, year=1,
                       lectures_per_week=lec, labs_per_week=lab, lab_tag=tag)
        subjects.append(subj)
        staff = first_year_teachers[code]
        for tid, tname, tdept in staff:
            if not any(t.id == tid for t in teachers):
                teachers.append(Teacher(id=tid, name=tname, department_id=tdept, shift_ids=["morning"], max_per_day=5))
        if code == "MA101":
            add_allotments(subj, staff[0][0], pairs)  # combined classes in big halls
        elif len(staff) == 2:
            add_allotments(subj, staff[0][0], [[fy[0]], [fy[1]]])
            add_allotments(subj, staff[1][0], [[fy[2]], [fy[3]]])
        else:
            add_allotments(subj, staff[0][0], [[s] for s in fy])

    # Prof. Vikram Singh also teaches Compiler Design to 3rd years: works both shifts.
    vikram = next(t for t in teachers if t.id == "t-vikram")
    vikram.shift_ids = ["morning", "evening"]
    vikram.max_per_day = 6
    compiler_teacher = next(a.teacher_id for a in allotments if a.subject_id == "cs305")
    teachers[:] = [t for t in teachers if t.id != compiler_teacher]
    for a in allotments:
        if a.teacher_id == compiler_teacher:
            a.teacher_id = "t-vikram"

    # Dr. Anita Sharma has a standing commitment on Wednesday mornings.
    anita = next(t for t in teachers if t.id == "t-anita")
    anita.blocked = [TimeBlock(day="Wed", start="08:30", end="10:10")]

    # 3rd-year open elective: students of 4 sections (3 departments) split into 3 groups,
    # each taught by a teacher of a different department in that department's rooms.
    elective_teachers = [
        ("t-gurpreet", "Dr. Gurpreet Sidhu", "me"),
        ("t-neeraj", "Prof. Neeraj Kohli", "cse"),
        ("t-alka", "Dr. Alka Jain", "ece"),
    ]
    for tid, tname, dept in elective_teachers:
        teachers.append(Teacher(id=tid, name=tname, department_id=dept, shift_ids=["evening"], max_per_day=5))
    elective_subjects = [("oe301", "OE301", "Robotics", "me"), ("oe302", "OE302", "Cloud Computing", "cse"),
                         ("oe303", "OE303", "IoT Systems", "ece")]
    for sid, code, name, dept in elective_subjects:
        subjects.append(Subject(id=sid, code=code, name=name, department_id=dept, year=3, lectures_per_week=0))
    students = _students()
    third = [sec.id for sec in SECTIONS if sec.year == 3]
    members: dict[str, list[str]] = {"robotics": [], "cloud": [], "iot": []}
    for st in students:
        if st.section_id in third:
            n = int(st.id.split("-")[-1])
            members["robotics" if n <= 15 else "cloud" if n <= 37 else "iot"].append(st.id)
    elective = ElectiveSlot(
        id="oe-3", name="Open Elective (3rd year)", section_ids=third, lectures_per_week=2,
        groups=[
            ElectiveGroup(id="robotics", name="Robotics", subject_id="oe301", teacher_id="t-gurpreet",
                          student_ids=members["robotics"]),
            ElectiveGroup(id="cloud", name="Cloud Computing", subject_id="oe302", teacher_id="t-neeraj",
                          student_ids=members["cloud"]),
            ElectiveGroup(id="iot", name="IoT Systems", subject_id="oe303", teacher_id="t-alka",
                          student_ids=members["iot"]),
        ],
    )

    # Who can teach what: everyone's current subjects (1st choice) plus one more subject
    # from their department (2nd choice), so suggestions have real alternatives.
    teacher_subjects: list[TeacherSubject] = []
    seen: set[tuple[str, str]] = set()
    for a in allotments:
        if (a.teacher_id, a.subject_id) not in seen:
            seen.add((a.teacher_id, a.subject_id))
            teacher_subjects.append(TeacherSubject(teacher_id=a.teacher_id, subject_id=a.subject_id, preference=1))
    for i, t in enumerate(teachers):
        mine = {sid for tid, sid in seen if tid == t.id}
        options = [sub.id for sub in subjects if sub.department_id == t.department_id and sub.id not in mine
                   and sub.lectures_per_week]
        extra = options[(i * 7) % len(options)] if options else None  # spread 2nd choices across subjects
        if extra:
            seen.add((t.id, extra))
            teacher_subjects.append(TeacherSubject(teacher_id=t.id, subject_id=extra, preference=2))
    for g in elective.groups:
        teacher_subjects.append(TeacherSubject(teacher_id=g.teacher_id, subject_id=g.subject_id, preference=1))

    return College(
        students=students,
        elective_slots=[elective],
        teacher_subjects=teacher_subjects,
        id="demo",
        name="Demo Institute of Technology",
        days=DAYS,
        lab_periods=2,
        shifts=[MORNING, EVENING],
        departments=DEPARTMENTS,
        venues=VENUES,
        sections=SECTIONS,
        teachers=teachers,
        subjects=subjects,
        allotments=allotments,
    )


FIRST_NAMES = [
    "Aarav", "Ananya", "Arjun", "Diya", "Harleen", "Ishaan", "Jasleen", "Kabir", "Kavya", "Manav",
    "Meher", "Navneet", "Nikita", "Pranav", "Priya", "Rahul", "Riya", "Sahil", "Sanya", "Simran",
    "Tanvi", "Uday", "Vansh", "Zoya", "Aditi", "Gurleen", "Karan", "Muskan", "Rohan", "Sneha",
]
LAST_NAMES = ["Sharma", "Gill", "Verma", "Singh", "Kaur", "Gupta", "Arora", "Mehta", "Bansal", "Sandhu"]


def _students() -> list[Student]:
    """Dummy student list: 60 per section, first half batch B1, second half B2.

    Login email pattern: <section id without dash>.<nn>@demo.timetabl.ai, e.g. cse3a.01@demo.timetabl.ai
    """
    out = []
    for sec in SECTIONS:
        code = sec.id.replace("-", "")
        for n in range(1, sec.strength + 1):
            batch = sec.batches[0] if n <= sec.batches[0].strength else sec.batches[1]
            name = f"{FIRST_NAMES[(n * 7 + len(code)) % len(FIRST_NAMES)]} {LAST_NAMES[(n * 3) % len(LAST_NAMES)]}"
            out.append(Student(
                id=f"{code}-{n:02d}", roll_no=f"{code.upper()}{n:02d}", name=name,
                email=f"{code}.{n:02d}@demo.timetabl.ai", section_id=sec.id, batch_id=batch.id,
            ))
    return out


def empty_college(name: str) -> College:
    """A new college before setup: Mon-Fri, one day shift of 7 periods. The setup wizard edits all of it."""
    slots = [("09:00", "09:50"), ("09:50", "10:40"), ("10:40", "11:30"), ("11:30", "12:20"),
             ("13:00", "13:50"), ("13:50", "14:40"), ("14:40", "15:30")]  # lunch 12:20-13:00
    periods = [Period(start=a, end=b) for a, b in slots]
    return College(
        id="new", name=name, days=["Mon", "Tue", "Wed", "Thu", "Fri"], lab_periods=2,
        shifts=[Shift(id="day", name="Day", periods=periods)],
        departments=[], venues=[], sections=[], teachers=[], subjects=[], allotments=[],
    )
