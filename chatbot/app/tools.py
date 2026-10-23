"""Assistant tools. Each role sees only its own tools; every call goes to the backend with the
user's own token, so the backend's permission checks always apply too.

No tool writes anything. Changes come back as *cards* (a prepared permanent move with its
before/after, or a prepared one-day change) that the user applies in the app.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

from app.backend import Backend, BackendError

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
STAFF = ("admin", "coordinator")


def _m(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _label(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{WEEKDAYS[x.weekday()]} {x.day} {x.strftime('%b')}"


# ---------------------------------------------------------------------------
# Inputs (validated before running: streamed tool inputs are not validated by the server)
# ---------------------------------------------------------------------------

class _Dates(BaseModel):
    from_date: str
    to_date: str | None = None

    @field_validator("from_date", "to_date")
    @classmethod
    def _iso(cls, v: str | None) -> str | None:
        if v is not None:
            date.fromisoformat(v)
        return v


class MyScheduleIn(_Dates):
    pass


class FreeTimeIn(_Dates):
    who: str | None = None  # section or teacher name (staff / teachers only)
    min_minutes: int = 45


class TimetableForIn(_Dates):
    kind: str
    name: str


class FreeRoomsIn(BaseModel):
    date: str | None = None
    time: str | None = None
    min_seats: int = 0


class WhereIsIn(BaseModel):
    teacher: str
    date: str | None = None
    time: str | None = None


class SessionIn(BaseModel):
    session_id: str


class ProposeMoveIn(BaseModel):
    session_id: str
    day: str
    start_time: str


class DayTimesIn(BaseModel):
    session_id: str
    date: str
    to_date: str | None = None


class OneDayIn(BaseModel):
    session_id: str
    date: str
    kind: str  # cancel | move
    to_date: str | None = None
    start_time: str | None = None
    reason: str = ""


class NoInput(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Tool definitions (JSON schema for the model) + who may use them
# ---------------------------------------------------------------------------

def _tool(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "eager_input_streaming": True,
        "input_schema": {"type": "object", "properties": props, "required": required, "additionalProperties": False},
    }


DATE = {"type": "string", "description": "Date as YYYY-MM-DD."}
TIME = {"type": "string", "description": "Time as HH:MM (24-hour)."}

TOOLS: dict[str, tuple[dict, type[BaseModel], tuple[str, ...]]] = {
    "my_schedule": (_tool(
        "my_schedule",
        "The user's own classes on real dates (weekly plan plus this week's cancellations and one-day moves, "
        "holidays excluded). Use for 'what do I have tomorrow', 'when is my next lab', 'anything cancelled'.",
        {"from_date": DATE, "to_date": {**DATE, "description": "Last date, inclusive (default: from_date)."}},
        ["from_date"]), MyScheduleIn, ("student", "teacher", "coordinator", "admin")),
    "free_time": (_tool(
        "free_time",
        "Free time windows on real dates within the college day (or shift), e.g. to plan a meeting or a makeup class. Without "
        "'who' it is the user's own free time. Lunch is shown separately.",
        {"from_date": DATE, "to_date": {**DATE, "description": "Last date, inclusive (default: from_date)."},
         "who": {"type": "string", "description": "Optional section (e.g. CSE-3A) or teacher name."},
         "min_minutes": {"type": "integer", "description": "Shortest window worth listing (default 45)."}},
        ["from_date"]), FreeTimeIn, ("student", "teacher", "coordinator", "admin")),
    "free_rooms": (_tool(
        "free_rooms",
        "Rooms and labs that are free at a date and time, and until when. Defaults to now.",
        {"date": DATE, "time": TIME, "min_seats": {"type": "integer", "description": "Minimum seats (optional)."}},
        []), FreeRoomsIn, ("student", "teacher", "coordinator", "admin")),
    "where_is_teacher": (_tool(
        "where_is_teacher",
        "Where a teacher is according to the timetable at a date and time (default now), and their next class.",
        {"teacher": {"type": "string", "description": "Teacher name, e.g. 'Anita Sharma'."}, "date": DATE, "time": TIME},
        ["teacher"]), WhereIsIn, ("student", "teacher", "coordinator", "admin")),
    "explain_class": (_tool(
        "explain_class",
        "Why a class is at its time and room: college hours or shift, lab rules, lunch, rules, teacher load, alternatives. "
        "Use a session_id from my_schedule or timetable_for.",
        {"session_id": {"type": "string"}}, ["session_id"]), SessionIn, ("student", "teacher", "coordinator", "admin")),
    "timetable_for": (_tool(
        "timetable_for",
        "Classes of a section, teacher or room on real dates (only what the user is allowed to see).",
        {"kind": {"type": "string", "enum": ["section", "teacher", "room"]},
         "name": {"type": "string", "description": "e.g. 'CSE-3A', 'Anita Sharma', 'LH-101'."},
         "from_date": DATE, "to_date": {**DATE, "description": "Last date, inclusive (default: from_date)."}},
        ["kind", "name", "from_date"]), TimetableForIn, ("teacher", "coordinator", "admin")),
    "quality_report": (_tool(
        "quality_report",
        "The current timetable's quality score with its breakdown and data-backed insights (heavy teacher days, "
        "idle rooms, uneven weeks, borrowed rooms).", {}, []), NoInput, STAFF),
    "department_status": (_tool(
        "department_status",
        "Which departments are Ready, and what is missing (sections, teachers, classes without a teacher).",
        {}, []), NoInput, STAFF),
    "move_options": (_tool(
        "move_options",
        "Every weekly slot a class could move to: free (direct), repair (other classes move), blocked (with reason).",
        {"session_id": {"type": "string"}}, ["session_id"]), SessionIn, STAFF),
    "propose_move": (_tool(
        "propose_move",
        "Prepare a PERMANENT move of a class in the weekly plan. The timetable engine repairs clashes and the user "
        "sees a before/after card to Apply or Discard; nothing changes until they apply it.",
        {"session_id": {"type": "string"}, "day": {"type": "string", "enum": WEEKDAYS},
         "start_time": TIME}, ["session_id", "day", "start_time"]), ProposeMoveIn, STAFF),
    "one_day_free_times": (_tool(
        "one_day_free_times",
        "Free times for moving one class for a single date (nobody else's classes move).",
        {"session_id": {"type": "string"}, "date": {**DATE, "description": "The class's original date."},
         "to_date": {**DATE, "description": "Date to move it to (default: same date)."}},
        ["session_id", "date"]), DayTimesIn, ("teacher", "coordinator", "admin")),
    "prepare_one_day_change": (_tool(
        "prepare_one_day_change",
        "Prepare a ONE-DAY change: cancel a class on a date, or move it to a free time on a date. The user sees a "
        "card and applies it; the weekly plan stays the same.",
        {"session_id": {"type": "string"}, "date": {**DATE, "description": "The class's original date."},
         "kind": {"type": "string", "enum": ["cancel", "move"]},
         "to_date": {**DATE, "description": "For move: target date (default: same date)."},
         "start_time": {**TIME, "description": "For move: new start time (must be a free time)."},
         "reason": {"type": "string", "description": "Short reason shown to students."}},
        ["session_id", "date", "kind"]), OneDayIn, ("teacher", "coordinator", "admin")),
}


def tools_for(role: str) -> list[dict]:
    """Tool definitions the model may see for this role (students never see edit tools)."""
    out = []
    for name, (spec, _, roles) in TOOLS.items():
        if role not in roles:
            continue
        if name == "free_time" and role == "student":
            continue
        out.append(spec)
    if role == "student":  # students get their own free time without the 'who' option
        spec = json.loads(json.dumps(TOOLS["free_time"][0]))
        spec["input_schema"]["properties"].pop("who")
        spec["description"] = ("The student's own free time windows on real dates within their college day, e.g. to "
                               "plan a meeting. Lunch is shown separately.")
        out.insert(1, spec)
    return out


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@dataclass
class ToolContext:
    backend: Backend
    member: dict  # this user's membership in the org (role, teacher_id, section_id, batch_id, ...)
    today: str  # YYYY-MM-DD in the college's local time
    now: str  # HH:MM
    _college: dict | None = None
    _timetable: dict | None = None
    _weeks: dict[str, dict] = field(default_factory=dict)
    cards: list[dict] = field(default_factory=list)  # proposals / one-day actions for the UI

    @property
    def role(self) -> str:
        return self.member["role"]

    async def college(self) -> dict:
        if self._college is None:
            self._college = await self.backend.college()
        return self._college

    async def timetable(self) -> dict:
        if self._timetable is None:
            self._timetable = await self.backend.timetable()
        return self._timetable

    async def week_of(self, d: str) -> dict:
        monday = (date.fromisoformat(d) - timedelta(days=date.fromisoformat(d).weekday())).isoformat()
        if monday not in self._weeks:
            self._weeks[monday] = await self.backend.week(monday)
        return self._weeks[monday]


class ToolError(Exception):
    pass


def _dates(from_date: str, to_date: str | None, limit: int = 14) -> list[str]:
    a = date.fromisoformat(from_date)
    b = date.fromisoformat(to_date) if to_date else a
    if b < a:
        a, b = b, a
    if (b - a).days >= limit:
        raise ToolError(f"Ask about at most {limit} days at a time.")
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def _find(items: list[dict], name: str, keys: tuple[str, ...]) -> dict:
    q = name.strip().lower().replace("dr. ", "").replace("prof. ", "")
    exact = [i for i in items if any(str(i.get(k, "")).lower() == q for k in keys)]
    if exact:
        return exact[0]
    loose = [i for i in items if any(q in str(i.get(k, "")).lower() for k in keys)]
    if len(loose) == 1:
        return loose[0]
    if loose:
        raise ToolError(f"'{name}' matches several: {', '.join(i.get('name', i.get('id')) for i in loose[:6])}. Be more specific.")
    raise ToolError(f"Couldn't find '{name}'.")


async def _occurrences(ctx: ToolContext, dates: list[str]) -> tuple[list[dict], dict[str, dict]]:
    """Occurrences on those dates (as the backend lets this user see them) and day info per date."""
    occ, days = [], {}
    for d in dates:
        wk = await ctx.week_of(d)
        for di in wk["days"]:
            days[di["date"]] = di
        occ += [o for o in wk["occurrences"] if o["date"] == d]
    return occ, days


def _describe(o: dict, c: dict) -> dict:
    s = o["session"]
    subj = next((x for x in c["subjects"] if x["id"] == s["subject_id"]), {})
    teacher = next((t["name"] for t in c["teachers"] if t["id"] == s["teacher_id"]), s["teacher_id"])
    room = next((v["name"] for v in c["venues"] if v["id"] == s["venue_id"]), s["venue_id"])
    secs = " + ".join(next((x["name"] for x in c["sections"] if x["id"] == i), i) for i in s["section_ids"])
    batch = None
    if s.get("batch_id"):
        sec = next((x for x in c["sections"] if x["id"] == s["section_ids"][0]), {"batches": []})
        batch = next((b["name"] for b in sec["batches"] if b["id"] == s["batch_id"]), None)
    out = {"session_id": s["id"], "date": o["date"], "day": _label(o["date"]), "start": s["start"], "end": s["end"],
           "subject": f"{subj.get('code', '')} {subj.get('name', '')}".strip(), "type": s["kind"], "teacher": teacher,
           "room": room, "sections": secs}
    if batch:
        out["batch"] = batch
    if s.get("elective_slot_id"):
        out["elective"] = True
    if o["status"] != "normal":
        out["status"] = {"cancelled": "cancelled", "moved_out": "moved away", "moved_in": "moved here (one day)"}[o["status"]]
        out["note"] = o["note"]
    return out


async def _mine(ctx: ToolContext, occ: list[dict]) -> list[dict]:
    """The user's own classes: students see only their own already; teachers filter to their lectures."""
    if ctx.role == "student":
        return occ
    tid = ctx.member.get("teacher_id")
    if not tid:
        raise ToolError("Your account isn't linked to a teacher in the timetable, so you have no own classes. "
                        "Use timetable_for with a section, teacher or room.")
    return [o for o in occ if o["session"]["teacher_id"] == tid]


async def _free_windows(ctx: ToolContext, dates: list[str], busy_for, shift_ids: list[str], years: set[int],
                        min_minutes: int) -> list[dict]:
    c = await ctx.college()
    tt = await ctx.timetable()
    occ, days = await _occurrences(ctx, dates)
    out = []
    for d in dates:
        info = days.get(d)
        if info is None:
            out.append({"day": _label(d), "free": [], "note": "Not a working day."})
            continue
        if info.get("holiday"):
            out.append({"day": _label(d), "free": [], "note": f"Holiday: {info['holiday']}."})
            continue
        busy = [(_m(o["session"]["start"]), _m(o["session"]["end"])) for o in occ
                if o["date"] == d and o["status"] in ("normal", "moved_in") and busy_for(o)]
        lunches = [ln for ln in tt["timetable"]["lunches"] if ln["shift_id"] in shift_ids and ln["year"] in years]
        day_free, lunch_txt = [], []
        for sh in (s for s in c["shifts"] if s["id"] in shift_ids):
            start, end = _m(sh["periods"][0]["start"]), _m(sh["periods"][-1]["end"])
            blocks = sorted(busy + [(_m(ln["start"]), _m(ln["end"])) for ln in lunches if ln["shift_id"] == sh["id"]])
            t = start
            for a, b in blocks:
                if a > t and a - t >= min_minutes:
                    day_free.append(f"{_hhmm(t)}-{_hhmm(min(a, end))}")
                t = max(t, b)
            if end - t >= min_minutes:
                day_free.append(f"{_hhmm(t)}-{_hhmm(end)}")
            lunch_txt += [f"lunch {ln['start']}-{ln['end']}" for ln in lunches if ln["shift_id"] == sh["id"]]
        out.append({"day": _label(d), "free": sorted(set(day_free)), "classes": len(busy),
                    **({"lunch": ", ".join(sorted(set(lunch_txt)))} if lunch_txt else {})})
    return out


async def run_tool(ctx: ToolContext, name: str, raw: Any) -> str:
    """Validate the input, run the tool, return a JSON string for the model. Raises ToolError for user-facing errors."""
    if name not in TOOLS or ctx.role not in TOOLS[name][2]:
        raise ToolError("That tool isn't available for your role.")
    model = TOOLS[name][1]
    try:
        args = model.model_validate(raw if isinstance(raw, dict) else {})
    except ValidationError as exc:
        raise ToolError(f"Invalid input: {exc.errors()[0].get('msg', 'bad value')}") from exc
    try:
        result = await _run(ctx, name, args)
    except BackendError as exc:
        raise ToolError(exc.message) from exc
    return json.dumps(result, ensure_ascii=False)


async def _run(ctx: ToolContext, name: str, a: Any) -> Any:
    c = await ctx.college()

    if name == "my_schedule":
        dates = _dates(a.from_date, a.to_date)
        occ, days = await _occurrences(ctx, dates)
        mine = sorted(await _mine(ctx, occ), key=lambda o: (o["date"], o["session"]["start"]))
        holidays = {d: i["holiday"] for d, i in days.items() if i.get("holiday") and d in dates}
        return {"classes": [_describe(o, c) for o in mine], "holidays": holidays,
                "dates_without_classes": [_label(d) for d in dates if not any(o["date"] == d for o in mine)]}

    if name == "free_time":
        dates = _dates(a.from_date, a.to_date)
        who = a.who
        if ctx.role == "student" and who:
            raise ToolError("Students can only check their own free time.")
        if ctx.role == "student" or not who:
            if ctx.role == "student":
                sec = next(s for s in c["sections"] if s["id"] == ctx.member["section_id"])
                return {"who": "you", "days": await _free_windows(ctx, dates, lambda o: True, [sec["shift_id"]],
                                                                  {sec["year"]}, a.min_minutes)}
            tid = ctx.member.get("teacher_id")
            if not tid:
                raise ToolError("Say whose free time: a section or a teacher.")
            t = next(x for x in c["teachers"] if x["id"] == tid)
            return {"who": "you", "days": await _free_windows(ctx, dates, lambda o: o["session"]["teacher_id"] == tid,
                                                              t["shift_ids"], set(), a.min_minutes)}
        try:
            sec = _find(c["sections"], who, ("name", "id"))
            return {"who": sec["name"], "days": await _free_windows(
                ctx, dates, lambda o: sec["id"] in o["session"]["section_ids"], [sec["shift_id"]], {sec["year"]},
                a.min_minutes)}
        except ToolError:
            t = _find(c["teachers"], who, ("name", "id"))
            return {"who": t["name"], "days": await _free_windows(
                ctx, dates, lambda o: o["session"]["teacher_id"] == t["id"], t["shift_ids"], set(), a.min_minutes)}

    if name == "timetable_for":
        dates = _dates(a.from_date, a.to_date)
        occ, _ = await _occurrences(ctx, dates)
        if a.kind == "section":
            x = _find(c["sections"], a.name, ("name", "id"))
            sel = [o for o in occ if x["id"] in o["session"]["section_ids"]]
        elif a.kind == "teacher":
            x = _find(c["teachers"], a.name, ("name", "id"))
            sel = [o for o in occ if o["session"]["teacher_id"] == x["id"]]
        else:
            x = _find(c["venues"], a.name, ("name", "id"))
            sel = [o for o in occ if o["session"]["venue_id"] == x["id"]]
        sel.sort(key=lambda o: (o["date"], o["session"]["start"]))
        return {"for": x["name"], "classes": [_describe(o, c) for o in sel]}

    if name == "free_rooms":
        rooms = await ctx.backend.free_rooms(a.date or ctx.today, a.time or ctx.now, a.min_seats)
        depts = {d["id"]: d["name"] for d in c["departments"]}
        return {"date": _label(a.date or ctx.today), "time": a.time or ctx.now,
                "note": "Shared rooms are for every department. A department's own room can be used by others "
                        "when free (first come); its department is told.",
                "free": [{"room": r["name"], "type": r["type"], "seats": r["capacity"],
                          "belongs_to": depts.get(r["department"], r["department"]) if r["department"] else "Shared",
                          "free_until": r["free_until"] or "end of day"} for r in rooms[:25]]}

    if name == "where_is_teacher":
        t = _find(c["teachers"], a.teacher, ("name", "id"))
        return await ctx.backend.teacher_now(t["id"], a.date or ctx.today, a.time or ctx.now)

    if name == "explain_class":
        return await ctx.backend.explain(a.session_id)

    if name == "quality_report":
        tt = await ctx.timetable()
        if tt.get("stale"):
            return {"note": "College data changed since this timetable was generated; regenerate for a fresh report."}
        return {"quality": tt.get("quality"), "insights": await ctx.backend.insights()}

    if name == "department_status":
        return await ctx.backend.readiness()

    if name == "move_options":
        opts = await ctx.backend.move_options(a.session_id)
        return {"free": [f"{o['day']} {o['start']}" + (f" ({o['reason']})" if o["reason"] else "")
                         for o in opts if o["status"] == "free"],
                "repair": [f"{o['day']} {o['start']}: {o['reason']}" for o in opts if o["status"] == "repair"][:15],
                "blocked_examples": [f"{o['day']} {o['start']}: {o['reason']}" for o in opts if o["status"] == "blocked"][:6]}

    if name == "propose_move":
        opts = await ctx.backend.move_options(a.session_id)
        opt = next((o for o in opts if o["day"] == a.day and o["start"] == a.start_time), None)
        if opt is None:
            raise ToolError(f"{a.day} {a.start_time} isn't a period start for this class. Use move_options.")
        if opt["status"] == "blocked":
            raise ToolError(f"Not possible: {opt['reason']}")
        p = await ctx.backend.propose(a.session_id, a.day, opt["start_period"])
        ctx.cards.append({"type": "proposal", "proposal": p})
        return {"prepared": True, "message": p["message"], "changes": p["changes"],
                "quality_before": p["quality_before"], "quality_after": p["quality_after"],
                "note": "A card with Apply / Discard is shown to the user. It is NOT applied yet."}

    if name == "one_day_free_times":
        opts = await ctx.backend.day_options(a.session_id, a.date, a.to_date or a.date)
        return {"date": _label(a.to_date or a.date),
                "free": [f"{o['start']}-{o['end']}" for o in opts if o["status"] == "free"],
                "not_free": [f"{o['start']}: {o['reason']}" for o in opts if o["status"] != "free"][:8]}

    if name == "prepare_one_day_change":
        tt = await ctx.timetable()
        s = next((x for x in tt["timetable"]["sessions"] if x["id"] == a.session_id), None)
        if s is None:
            raise ToolError("Class not found. Use my_schedule or timetable_for to get its session_id.")
        if WEEKDAYS[date.fromisoformat(a.date).weekday()] != s["day"]:
            raise ToolError(f"This class is on {s['day']}s; {_label(a.date)} is a different day.")
        if ctx.role == "teacher" and s["teacher_id"] != ctx.member.get("teacher_id"):
            raise ToolError("Teachers can change only their own lectures.")
        subj = next((x["name"] for x in c["subjects"] if x["id"] == s["subject_id"]), s["subject_id"])
        action: dict[str, Any] = {"session_id": a.session_id, "date": a.date, "kind": a.kind, "reason": a.reason}
        if a.kind == "cancel":
            summary = f"Cancel {subj} on {_label(a.date)} ({s['start']}-{s['end']})"
        elif a.kind == "move":
            to = a.to_date or a.date
            if not a.start_time:
                raise ToolError("Give the new start time (use one_day_free_times).")
            opts = await ctx.backend.day_options(a.session_id, a.date, to)
            opt = next((o for o in opts if o["start"] == a.start_time), None)
            if opt is None or opt["status"] != "free":
                raise ToolError(f"{_label(to)} {a.start_time} isn't free" + (f": {opt['reason']}" if opt else "."))
            action.update({"to_date": to, "start_period": opt["start_period"]})
            summary = f"Move {subj} from {_label(a.date)} {s['start']} to {_label(to)} {opt['start']}-{opt['end']}"
        else:
            raise ToolError("kind must be cancel or move.")
        action["summary"] = summary + (f" · {a.reason}" if a.reason else "")
        ctx.cards.append({"type": "one_day", "action": action})
        return {"prepared": True, "summary": action["summary"],
                "note": "A card with Apply is shown to the user. It is NOT applied yet; students are told once applied."}

    raise ToolError(f"Unknown tool {name}.")
