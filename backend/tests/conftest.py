import os
import sys
import tempfile
from pathlib import Path

import pytest

# Tests use a throwaway database and a fixed secret; set before anything imports app.core.config.
_tmp = Path(tempfile.mkdtemp(prefix="timetabl-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["APP_SECRET"] = "test-secret"
os.environ.setdefault("DEMO_PASSWORD", "demo1234")
os.environ["AUTO_DEMO_TIMETABLE"] = "0"  # tests generate when they need to

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.domain import (  # noqa: E402
    Allotment,
    Batch,
    College,
    Department,
    Kind,
    LunchRule,
    Period,
    Section,
    Shift,
    Subject,
    Teacher,
    Venue,
    VenueType,
)


def tiny_college(**overrides) -> College:
    """One department, one section with 2 batches, 1 shift of 6 periods over 3 days."""
    shift = Shift(
        id="day",
        name="Day",
        periods=[
            Period(start="09:00", end="10:00"),
            Period(start="10:00", end="11:00"),
            Period(start="11:00", end="12:00"),
            Period(start="12:00", end="13:00"),
            Period(start="13:00", end="14:00"),
            Period(start="14:00", end="15:00"),
        ],
        lunch=LunchRule(window_start="12:00", window_end="14:00"),
    )
    sec = Section(
        id="s1", name="CSE-1A", department_id="cse", year=1, strength=40, shift_id="day",
        batches=[Batch(id="b1", name="B1", strength=20), Batch(id="b2", name="B2", strength=20)],
    )
    data = dict(
        id="tiny",
        name="Tiny College",
        days=["Mon", "Tue", "Wed"],
        lab_periods=2,
        shifts=[shift],
        departments=[Department(id="cse", name="CSE", short="CSE")],
        venues=[
            Venue(id="r1", name="Room 1", type=VenueType.lecture, capacity=45, department_id="cse"),
            Venue(id="lab", name="Lab", type=VenueType.lab, capacity=25, tags=["computers"], department_id="cse"),
        ],
        sections=[sec],
        teachers=[
            Teacher(id="t1", name="Dr. A", department_id="cse", shift_ids=["day"], max_per_day=4),
            Teacher(id="t2", name="Dr. B", department_id="cse", shift_ids=["day"], max_per_day=4),
        ],
        subjects=[
            Subject(id="maths", code="MA", name="Maths", department_id="cse", year=1, lectures_per_week=3),
            Subject(id="prog", code="CS", name="Programming", department_id="cse", year=1,
                    lectures_per_week=2, labs_per_week=1, lab_tag="computers"),
        ],
        allotments=[
            Allotment(id="a1", subject_id="maths", teacher_id="t1", kind=Kind.lecture, section_ids=["s1"]),
            Allotment(id="a2", subject_id="prog", teacher_id="t2", kind=Kind.lecture, section_ids=["s1"]),
            Allotment(id="a3", subject_id="prog", teacher_id="t2", kind=Kind.lab, section_ids=["s1"], batch_id="b1"),
            Allotment(id="a4", subject_id="prog", teacher_id="t2", kind=Kind.lab, section_ids=["s1"], batch_id="b2"),
        ],
    )
    data.update(overrides)
    return College(**data)


@pytest.fixture
def college() -> College:
    return tiny_college()
