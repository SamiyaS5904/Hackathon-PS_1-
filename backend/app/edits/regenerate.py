"""Mid-semester regenerate with minimal change.

When college data changes during the semester (a new teacher, a section that grew, a new rule), a fresh
timetable could move almost every class. Instead the solver gets the current placements and pays a high
price for every class that leaves its day/time (app.solver.generate ``keep``), so only classes that have
to move do. Afterwards:

- classes keep their ids where they can (same allotment), so attendance history and future hooks stay
  attached;
- one-day changes (cancellations, makeup moves) are carried over when their class is unchanged and they
  still fit; the rest are listed as dropped;
- a plain summary says how many classes stayed, moved, were added or removed.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from app.edits.moves import Change, diff
from app.edits.oneday import add_override, label
from app.models.domain import College, Session, Timetable
from app.solver.generate import Keep


class RegenerateSummary(BaseModel):
    kept: int
    moved: int
    added: int
    removed: int
    one_day_kept: int
    one_day_dropped: list[str]
    changes: list[Change]

    def sentence(self) -> str:
        parts = [f"{self.kept} classes stayed where they were", f"{self.moved} moved"]
        if self.added:
            parts.append(f"{self.added} new")
        if self.removed:
            parts.append(f"{self.removed} removed")
        out = ", ".join(parts) + "."
        if self.one_day_dropped:
            out += f" {len(self.one_day_dropped)} one-day change(s) no longer fit and were dropped."
        return out


def keep_map(tt: Timetable) -> Keep:
    """The current placements, for the solver."""
    keep: Keep = {}
    for s in tt.sessions:
        keep[(s.allotment_id, s.day, s.start_period)] = s.venue_id
        if s.elective_slot_id:
            keep[(f"e:{s.elective_slot_id}", s.day, s.start_period)] = None
    return keep


def _number(sid: str) -> int:
    return int(sid[1:]) if sid[:1] == "s" and sid[1:].isdigit() else 0


def stable_ids(old: list[Session], new: list[Session]) -> list[Session]:
    """Old ids for unchanged placements, then for moved classes of the same allotment; fresh ids after that
    (never an id a removed class had, so old attendance never points at a different class)."""
    by_allot: dict[str, list[Session]] = defaultdict(list)
    for s in old:
        by_allot[s.allotment_id].append(s)
    used: set[str] = set()
    out: list[Session | None] = [None] * len(new)
    for i, n in enumerate(new):
        o = next((o for o in by_allot[n.allotment_id]
                  if o.id not in used and (o.day, o.start_period) == (n.day, n.start_period)), None)
        if o is not None:
            used.add(o.id)
            out[i] = n.model_copy(update={"id": o.id})
    for i, n in enumerate(new):
        if out[i] is None:
            o = next((o for o in by_allot[n.allotment_id] if o.id not in used), None)
            if o is not None:
                used.add(o.id)
                out[i] = n.model_copy(update={"id": o.id})
    nxt = max([_number(s.id) for s in old] + [0]) + 1
    for i, n in enumerate(new):
        if out[i] is None:
            out[i] = n.model_copy(update={"id": f"s{nxt}"})
            nxt += 1
    return [s for s in out if s is not None]


def finish(college: College, old: Timetable, new: Timetable, actor: str) -> tuple[Timetable, RegenerateSummary]:
    """Stable ids, carried one-day changes, and the summary."""
    sessions = stable_ids(old.sessions, new.sessions)
    tt = new.model_copy(update={"sessions": sessions, "overrides": []})
    old_by_id = {s.id: s for s in old.sessions}
    new_by_id = {s.id: s for s in sessions}
    unchanged = {sid for sid, s in new_by_id.items() if sid in old_by_id
                 and (old_by_id[sid].day, old_by_id[sid].start_period) == (s.day, s.start_period)}

    dropped: list[str] = []
    kept_overrides = 0
    for o in sorted(old.overrides, key=lambda o: (o.date, o.id)):
        s = old_by_id.get(o.session_id)
        what = f"{college.subject(s.subject_id).name} on {label(o.date)}" if s else f"a class on {label(o.date)}"
        if o.session_id not in unchanged:
            dropped.append(f"{what} ({o.kind}): the class moved")
            continue
        out, msg, _ = add_override(college, tt, o.session_id, o.date, o.kind, o.to_date, o.start_period, o.reason,
                                   o.created_by or actor)
        if out is None:
            dropped.append(f"{what} ({o.kind}): {msg}")
        else:
            tt, kept_overrides = out, kept_overrides + 1

    changes = diff(college, old.sessions, sessions)
    moved = sum(1 for sid in new_by_id if sid in old_by_id and sid not in unchanged)
    summary = RegenerateSummary(
        kept=len(unchanged), moved=moved, added=sum(1 for sid in new_by_id if sid not in old_by_id),
        removed=sum(1 for sid in old_by_id if sid not in new_by_id), one_day_kept=kept_overrides,
        one_day_dropped=dropped, changes=changes)
    return tt, summary
