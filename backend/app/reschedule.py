"""Reschedule finder: when are the teacher, every student of the class and a room all free?

One list for the coming days (today up to a week after the class's date), each time marked when the
same weekday and period is also free every week, so a teacher can move the class for that one day
(instant) or ask the Department Coordinator to move it for good, from the same screen.

Built on the one-day rules (app/edits/oneday.py: free slots only, nobody else's class moves, lunch
stays free, rooms held for events stay held) and the weekly move check (app/edits/moves.py).
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

from app.edits.moves import move_options
from app.edits.oneday import day_options, label, weekday
from app.models.domain import College, Timetable, to_minutes


class RescheduleOption(BaseModel):
    date: str
    label: str  # "Fri 30 Oct"
    day: str  # weekday, "Fri"
    start_period: int
    start: str
    end: str
    venue_id: str | None
    venue: str
    every_week: bool  # the same weekday and period is free every week too (a permanent move fits)


class RescheduleOut(BaseModel):
    options: list[RescheduleOption]
    note: str = ""  # why there is nothing to pick, in plain words


def reschedule_options(college: College, tt: Timetable, session_id: str, from_date: str, today: str, now: str,
                       days: int = 7, limit: int = 40) -> RescheduleOut:
    s = next(x for x in tt.sessions if x.id == session_id)
    if s.elective_slot_id:
        return RescheduleOut(options=[], note="Elective groups meet together, so one group can't be moved on its "
                                              "own. Cancel it for the day instead.")
    weekly = {(o.day, o.start_period) for o in move_options(college, tt, session_id) if o.status == "free"}
    venues = {v.id: v.name for v in college.venues}
    first = date.fromisoformat(today)
    last = max(date.fromisoformat(from_date), first) + timedelta(days=days)
    out: list[RescheduleOption] = []
    d0 = first
    while d0 <= last and len(out) < limit:
        d, d0 = d0.isoformat(), d0 + timedelta(days=1)
        wd = weekday(college, d)
        if wd is None or any(h.date == d for h in college.holidays):
            continue
        for o in day_options(college, tt, session_id, from_date, d):
            if o.status != "free" or (d == today and to_minutes(o.start) <= to_minutes(now)):
                continue
            out.append(RescheduleOption(date=d, label=label(d), day=wd, start_period=o.start_period, start=o.start,
                                        end=o.end, venue_id=o.venue_id, venue=venues.get(o.venue_id or "", ""),
                                        every_week=(wd, o.start_period) in weekly))
            if len(out) >= limit:
                break
    note = "" if out else ("No time in the coming days has the teacher, every student and a suitable room free "
                           "together. Cancel the class for the day, or ask your Coordinator.")
    return RescheduleOut(options=out, note=note)
