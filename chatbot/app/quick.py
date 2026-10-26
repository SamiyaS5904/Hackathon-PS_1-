"""Instant answers: the most common look-ups answered straight from the timetable, without calling the AI model.

"What's my next class?", "What do I have tomorrow?", "Which rooms are free now?", "Where is Dr. Kaur?",
"Show CSE-3A timetable", "Undo that", "My attendance". They use the assistant's own tools (same permissions, same
data), so the answer is exactly what the assistant would have looked up, in well under a second and at no API cost.
Only clear, whole-message matches are answered here; anything else (or any doubt) goes to the model.
"""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from datetime import date, timedelta
from typing import Any

from app.tools import ToolContext, ToolError, run_tool

STAFF = ("admin", "coordinator")


async def _tool(ctx: ToolContext, name: str, args: dict) -> Any:
    return json.loads(await run_tool(ctx, name, args))


def _clean(text: str) -> str:
    t = text.strip().lower().replace("’", "'")
    t = re.sub(r"[?.!]+$", "", t).strip()
    return re.sub(r"\s+", " ", t)


_codes: ContextVar[frozenset[str]] = ContextVar("subject_codes", default=frozenset())  # this request's college


def _subject(full: str) -> str:
    """'CS202 Database Systems' -> 'Database Systems' (the code is noise when spoken)."""
    parts = full.split(" ", 1)
    return parts[1] if len(parts) == 2 and parts[0] in _codes.get() else full


def _live(c: dict) -> bool:
    return c.get("status") not in ("cancelled", "moved away")


def _line(c: dict, role: str) -> str:
    who = f", {c['teacher']}" if role == "student" else f", {c['sections']}" + (f" ({c['batch']})" if c.get("batch") else "")
    return f"{c['start']} {_subject(c['subject'])} in {c['room']}{who}"


async def _next_class(ctx: ToolContext) -> dict | None:
    end = (date.fromisoformat(ctx.today) + timedelta(days=6)).isoformat()
    out = await _tool(ctx, "my_schedule", {"from_date": ctx.today, "to_date": end})
    classes = [c for c in out["classes"] if _live(c)]
    now = [c for c in classes if c["date"] == ctx.today and c["start"] <= ctx.now < c["end"]]
    upcoming = [c for c in classes if c["date"] > ctx.today or c["start"] > ctx.now]
    if not classes or (not now and not upcoming):
        return {"text": "You have no more classes in the next 7 days."}
    parts = []
    if now:
        c = now[0]
        parts.append(f"You're in {_subject(c['subject'])} now, in {c['room']}, until {c['end']}.")
    if upcoming:
        c = upcoming[0]
        when = "today" if c["date"] == ctx.today else c["day"]
        with_ = f" with {c['teacher']}" if ctx.role == "student" else f" ({c['sections']})"
        parts.append(f"{'Next' if now else 'Your next class'}: {_subject(c['subject'])}{with_}, {when} at {c['start']} "
                     f"in {c['room']}.")
    return {"text": " ".join(parts)}


async def _day(ctx: ToolContext, which: str) -> dict:
    d = date.fromisoformat(ctx.today) + timedelta(days=1 if which == "tomorrow" else 0)
    out = await _tool(ctx, "my_schedule", {"from_date": d.isoformat()})
    holiday = out.get("holidays", {}).get(d.isoformat())
    label = which.capitalize()
    if holiday:
        return {"text": f"{label} is a holiday ({holiday}). No classes."}
    classes = sorted(out["classes"], key=lambda c: c["start"])
    live = [c for c in classes if _live(c)]
    if not live:
        return {"text": f"No classes {which}." + (" Your classes that day are cancelled or moved." if classes else "")}
    shown = live[:5]
    text = f"{label} you have {len(live)} class{'es' if len(live) != 1 else ''}, from {live[0]['start']}: " \
           + "; ".join(_line(c, ctx.role) for c in shown) + "."
    if len(live) > 5:
        text += f" And {len(live) - 5} more."
    gone = [c for c in classes if not _live(c)]
    if gone:
        text += " " + "; ".join(f"{_subject(c['subject'])} at {c['start']} is {c['status']}" for c in gone) + "."
    return {"text": text}


async def _free_rooms(ctx: ToolContext) -> dict:
    out = await _tool(ctx, "free_rooms", {})
    rooms = out["free"]
    if not rooms:
        return {"text": "No rooms are free right now."}
    # Where to sit: lecture rooms before labs, the person's own department's rooms first, then the ones free longest.
    c = await ctx.college()
    sec = next((s for s in c["sections"] if s["id"] == ctx.member.get("section_id")), None)
    dept_id = sec["department_id"] if sec else ctx.member.get("department_id")
    own = next((d["name"] for d in c["departments"] if d["id"] == dept_id), None)
    rooms = sorted(rooms, key=lambda r: (r["type"] == "lab", r["belongs_to"] != own, r["free_until"] != "end of day",
                                         -_mins(r["free_until"]), -r["seats"]))
    shown = rooms[:5]
    text = f"{len(rooms)} room{'s are' if len(rooms) != 1 else ' is'} free right now. " + "; ".join(
        f"{r['room']} ({r['seats']} seats) "
        + ("all day" if r["free_until"] == "end of day" else f"until {r['free_until']}") for r in shown) + "."
    if len(rooms) > 5:
        text += f" And {len(rooms) - 5} more."
    return {"text": text}


def _mins(hhmm: str) -> int:
    m = re.match(r"(\d{1,2}):(\d{2})", hhmm or "")
    return int(m[1]) * 60 + int(m[2]) if m else 24 * 60


async def _where(ctx: ToolContext, name: str) -> dict | None:
    try:
        t = await _tool(ctx, "where_is_teacher", {"teacher": name})
    except ToolError:
        return None  # not a teacher's name the tools know: let the model handle it
    who = t["teacher"]
    if t["status"] == "teaching":
        text = f"{who} is teaching {t['subject']} to {t['sections']} in {t['room']} until {t['until']}."
    elif t["status"] == "free":
        text = f"{who} is free right now." + (f" Next class: {t['next_class']}." if t.get("next_class") else
                                               " No more classes today.")
    elif t["status"] == "holiday":
        text = f"Today is a holiday, so {who} has no classes."
    else:
        text = f"{who} has no classes today."
    return {"text": text}


async def _show(ctx: ToolContext, name: str) -> dict | None:
    c = await ctx.college()
    low = name.lower().strip()
    kind = None
    for k, items in (("section", c["sections"]), ("teacher", c["teachers"]), ("room", c["venues"])):
        if any(low == x["name"].lower() or (k == "teacher" and low in x["name"].lower()) for x in items):
            kind = k
            break
    if kind is None:
        return None
    out = await _tool(ctx, "show_on_screen", {"page": "timetable", "kind": kind, "name": name})
    return {"text": f"Opened {out['shown']}."}


async def _undo(ctx: ToolContext) -> dict:
    out = await _tool(ctx, "prepare_undo", {})
    if not out.get("prepared"):
        return {"text": out.get("note", "There is no change to undo.")}
    return {"text": f"The latest change is: {out['latest_change']} (by {out['by']}). Tap Undo on the card to reverse it."}


async def _attendance(ctx: ToolContext) -> dict:
    out = await _tool(ctx, "my_attendance", {})
    if not out["overall"].endswith("%"):
        return {"text": f"No attendance has been marked for you yet. The minimum is {out['minimum']}."}
    return {"text": f"Your attendance is {out['overall']} (the minimum is {out['minimum']}). {out['advice']}".strip()}


_PAGES = {"bookings": "bookings", "changes": "changes", "home": "home", "attendance": "attendance",
          "room bookings": "rooms", "events": "rooms"}


async def answer(ctx: ToolContext, message: str) -> dict | None:
    """{"text": ...} for a common look-up (cards, if any, are in ctx.cards), or None to ask the model."""
    q = _clean(message)
    if len(q) > 80 or ctx.role == "platform":
        return None
    try:
        _codes.set(frozenset(s["code"] for s in (await ctx.college())["subjects"]))
        if re.fullmatch(r"(what'?s|what is|when'?s|when is|where'?s|where is)?\s*(my )?next (class|lecture|period|lab)"
                        r"( and where)?", q):
            return await _next_class(ctx)
        m = re.fullmatch(r"(what do i have|what do i teach|what classes do i have|my (classes|schedule|timetable)|"
                         r"what are my classes|what'?s my (schedule|timetable))\s*(for )?(today|tomorrow)", q)
        if m:
            return await _day(ctx, m.group(m.lastindex))
        if re.fullmatch(r"((which|what|any) (rooms?|classrooms?|labs?|halls?) (are |is )?(free|empty|available)|"
                        r"free (rooms?|classrooms?)|(is there )?(an? )?(free|empty) (room|classroom)|"
                        r"where (can|should) (i|we) (sit|study|go))"
                        r"( right)?( now)?", q):
            return await _free_rooms(ctx)
        m = re.fullmatch(r"where('?s| is) (.{3,40}?)( right)?( now)?", q)
        if m and not m.group(2).startswith(("my ", "the ", "it", "this")):
            return await _where(ctx, m.group(2))
        if ctx.role in STAFF:
            m = re.fullmatch(r"(show|open)( me)? (the )?(.{2,40}?)('s)? (time ?table|schedule)( this week)?", q)
            if m:
                return await _show(ctx, m.group(4))
            if re.fullmatch(r"undo( that| it| the last change| last change| my last change)?", q):
                return await _undo(ctx)
        m = re.fullmatch(r"(open|go to|show)( me)? (the )?(bookings|changes|home|attendance|room bookings|events)( page)?", q)
        if m:
            out = await _tool(ctx, "show_on_screen", {"page": _PAGES[m.group(4)]})
            return {"text": f"Opened {out['shown']}."}
        if ctx.role == "student" and re.fullmatch(r"(what'?s |what is |show |check )?my attendance", q):
            return await _attendance(ctx)
    except (ToolError, KeyError, ValueError):
        return None  # anything unexpected: the model answers instead
    return None
