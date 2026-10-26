"""Domain models for the timetable engine.

These describe one college's scheduling input (``College``) and the engine's
output (``Timetable``). They are deliberately storage-agnostic: Stage 1 builds
them in memory, later stages load them from Supabase.

Times are "HH:MM" strings in the college's local time. Days are short names
("Mon", "Tue", ...). A *period* is one teaching slot inside a shift; breaks are
the gaps between periods (or year-specific breaks laid over periods).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class Period(BaseModel):
    start: str
    end: str

    @property
    def start_min(self) -> int:
        return to_minutes(self.start)

    @property
    def end_min(self) -> int:
        return to_minutes(self.end)


class YearBreak(BaseModel):
    """A break that applies only to some years (e.g. staggered lunch).

    Any period overlapping [start, end) is unavailable for sections of these years.
    """

    years: list[int]
    start: str
    end: str
    label: str = "Break"


class LunchRule(BaseModel):
    """Flexible lunch: every section gets one free period inside the mess window, every day.

    The solver picks the period per section and per day (11:30 one day, 13:30 the next is fine),
    whatever makes the best timetable. That also spreads lunch over the window, so rooms and the
    mess are used evenly.
    """

    window_start: str
    window_end: str


class Shift(BaseModel):
    id: str
    name: str
    periods: list[Period]
    year_breaks: list[YearBreak] = Field(default_factory=list)  # fixed breaks for some years
    lunch: LunchRule | None = None  # flexible lunch chosen by the solver

    def lunch_candidates(self) -> list[int]:
        """Period indices fully inside the mess window."""
        if self.lunch is None:
            return []
        lo, hi = to_minutes(self.lunch.window_start), to_minutes(self.lunch.window_end)
        return [i for i, p in enumerate(self.periods) if lo <= p.start_min and p.end_min <= hi]


class VenueType(str, Enum):
    lecture = "lecture"
    lab = "lab"
    seminar = "seminar"


class Venue(BaseModel):
    id: str
    name: str
    type: VenueType
    capacity: int
    tags: list[str] = Field(default_factory=list)
    department_id: str | None = None  # None = shared venue


class Department(BaseModel):
    id: str
    name: str
    short: str


class Batch(BaseModel):
    id: str
    name: str
    strength: int


class Section(BaseModel):
    id: str
    name: str
    department_id: str
    year: int
    strength: int
    shift_id: str
    batches: list[Batch] = Field(default_factory=list)


class Student(BaseModel):
    """One student, from the student-level list. Their login uses ``email``."""

    id: str
    roll_no: str
    name: str
    email: str
    section_id: str
    batch_id: str | None = None


class Teacher(BaseModel):
    id: str
    name: str
    department_id: str
    shift_ids: list[str]  # shifts this teacher may teach in
    max_per_day: int = 6
    blocked: list[TimeBlock] = Field(default_factory=list)


class TimeBlock(BaseModel):
    day: str
    start: str
    end: str


class Subject(BaseModel):
    id: str
    code: str
    name: str
    department_id: str
    year: int
    lectures_per_week: int = 0
    labs_per_week: int = 0  # number of lab blocks (each = college lab length)
    lab_tag: str | None = None  # required venue tag for labs, e.g. "computers"


class Kind(str, Enum):
    lecture = "lecture"
    lab = "lab"


class Allotment(BaseModel):
    """Who teaches what to whom.

    - Lecture for one section, or several sections together (combined class).
    - Lab for one batch, or for a whole section if it has no batches.
    """

    id: str
    subject_id: str
    teacher_id: str | None  # None until the Coordinator assigns one (or accepts a suggestion)
    kind: Kind
    section_ids: list[str]
    batch_id: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Allotment:
        if not self.section_ids:
            raise ValueError("allotment needs at least one section")
        if self.batch_id and len(self.section_ids) != 1:
            raise ValueError("a batch allotment belongs to exactly one section")
        return self


class ElectiveGroup(BaseModel):
    """One option inside an elective slot, or a pooled class.

    Taught by any department's teacher; members are individual students from the
    slot's sections (several departments). The room must hold ``len(student_ids)``.
    """

    id: str
    name: str
    subject_id: str
    teacher_id: str
    student_ids: list[str]


class ElectiveSlot(BaseModel):
    """A fixed time when every student of ``section_ids`` is in one of the groups.

    All groups meet at the same time(s); the home sections don't meet then.
    """

    id: str
    name: str
    section_ids: list[str]
    lectures_per_week: int
    groups: list[ElectiveGroup]


class TeacherSubject(BaseModel):
    """A subject a teacher can teach (entered by the Department Coordinator). 1 = most preferred."""

    teacher_id: str
    subject_id: str
    preference: int = 2


class Rule(BaseModel):
    """A rule card. kind="no_classes": no classes on ``days`` (all if empty) between ``after`` and ``before``
    (either may be empty = start/end of day). kind="max_per_day": at most ``max_periods`` periods a day.

    Applies to the sections of ``department_id`` (all departments if None) and ``years`` (all if empty).
    mode="must" is never broken; mode="try" is a preference with ``weight`` (1-10).
    """

    id: str
    name: str
    kind: str  # "no_classes" | "max_per_day"
    mode: str = "must"  # "must" | "try"
    weight: int = 5
    enabled: bool = True
    department_id: str | None = None
    years: list[int] = Field(default_factory=list)
    days: list[str] = Field(default_factory=list)
    after: str | None = None
    before: str | None = None
    max_periods: int | None = None

    def applies_to(self, section) -> bool:
        return (self.department_id in (None, section.department_id)) and (not self.years or section.year in self.years)

    def blocks(self, day: str, begin: int, end: int) -> bool:
        """For no_classes: does [begin, end) on ``day`` fall in the rule's window?"""
        if self.kind != "no_classes" or (self.days and day not in self.days):
            return False
        lo = to_minutes(self.after) if self.after else 0
        hi = to_minutes(self.before) if self.before else 24 * 60
        return begin < hi and lo < end


class Holiday(BaseModel):
    date: str  # YYYY-MM-DD
    label: str


class DepartmentStatus(BaseModel):
    ready: bool = False
    at: float | None = None
    by: str = ""


class College(BaseModel):
    id: str
    name: str
    days: list[str]
    lab_periods: int = 2  # one lab length for the whole college, in periods
    shifts: list[Shift]
    departments: list[Department]
    venues: list[Venue]
    sections: list[Section]
    teachers: list[Teacher]
    subjects: list[Subject]
    allotments: list[Allotment]
    students: list[Student] = Field(default_factory=list)
    elective_slots: list[ElectiveSlot] = Field(default_factory=list)
    teacher_subjects: list[TeacherSubject] = Field(default_factory=list)
    holidays: list[Holiday] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    semester_start: str | None = None  # YYYY-MM-DD (tentative, editable)
    semester_end: str | None = None
    department_status: dict[str, DepartmentStatus] = Field(default_factory=dict)
    # Attendance rule: students need at least this share of held classes, overall and per subject.
    attendance_min_percent: int = 75
    # Setup checklist: None = an older college (treated as set up once it has departments).
    setup_saved: bool | None = None
    revision: int = 0  # bumped on every data change; a timetable remembers the revision it was built from

    # ---- lookups -------------------------------------------------------
    def shift(self, shift_id: str) -> Shift:
        return next(s for s in self.shifts if s.id == shift_id)

    def section(self, section_id: str) -> Section:
        return next(s for s in self.sections if s.id == section_id)

    def teacher(self, teacher_id: str) -> Teacher:
        return next(t for t in self.teachers if t.id == teacher_id)

    def subject(self, subject_id: str) -> Subject:
        return next(s for s in self.subjects if s.id == subject_id)

    def venue(self, venue_id: str) -> Venue:
        return next(v for v in self.venues if v.id == venue_id)

    def elective_slot(self, slot_id: str) -> ElectiveSlot:
        return next(e for e in self.elective_slots if e.id == slot_id)

    def elective_group(self, slot_id: str, group_id: str) -> ElectiveGroup:
        return next(g for g in self.elective_slot(slot_id).groups if g.id == group_id)


class Session(BaseModel):
    """One scheduled class in the weekly template."""

    id: str
    allotment_id: str
    subject_id: str
    teacher_id: str
    venue_id: str
    kind: Kind
    section_ids: list[str]
    batch_id: str | None = None
    day: str
    shift_id: str
    start_period: int  # 0-based index into the shift's periods
    length: int  # number of periods
    start: str
    end: str
    # Elective group sessions: section_ids = sections that have members in this group.
    elective_slot_id: str | None = None
    group_id: str | None = None


class Lunch(BaseModel):
    """One section's lunch on one weekday: a free period inside its shift's mess window, chosen by
    the solver, so it can differ between sections and between days. (Older timetables stored one
    lunch per year for every day: ``year`` set, no ``section_id``; they are upgraded on load.)"""

    shift_id: str
    period: int
    start: str
    end: str
    section_id: str | None = None
    day: str | None = None
    year: int | None = None


class Override(BaseModel):
    """A one-day change on top of the weekly template (the template itself is untouched).

    kind="cancel": the class doesn't happen on `date`.
    kind="move": on `date` the class happens on `to_date` at `start_period` in `venue_id` instead.
    kind="substitute": on `date` the class happens as usual, taught by `teacher_id` (the usual teacher is away).
    """

    id: str
    session_id: str
    date: str  # YYYY-MM-DD, the original occurrence
    kind: str  # "cancel" | "move" | "substitute"
    to_date: str | None = None
    teacher_id: str | None = None  # kind="substitute": who takes the class that day
    start_period: int | None = None
    venue_id: str | None = None
    reason: str = ""
    created_by: str = "Admin"


class Timetable(BaseModel):
    college_id: str
    status: str  # "optimal" | "feasible" | "infeasible" | "invalid_input" | "timeout"
    sessions: list[Session] = Field(default_factory=list)
    lunches: list[Lunch] = Field(default_factory=list)
    overrides: list[Override] = Field(default_factory=list)
    college_revision: int = 0  # College.revision this timetable was generated from
    messages: list[str] = Field(default_factory=list)  # blocking problems
    warnings: list[str] = Field(default_factory=list)  # worth knowing, not blocking
    solve_seconds: float = 0.0
    objective: float | None = None
    published_at: float | None = None  # set when the College Admin publishes; edits keep it
    published_by: str = ""


Teacher.model_rebuild()
