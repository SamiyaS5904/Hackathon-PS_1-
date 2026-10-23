"""Generate the demo college timetable from the terminal.

    python -m app.cli                 # generate, validate, score, print summary
    python -m app.cli --section cse-3a --time 20
"""

from __future__ import annotations

import argparse

from app.models.domain import College, Timetable
from app.seed.demo_college import build_demo_college
from app.solver.generate import generate
from app.solver.quality import score
from app.validator.check import validate


def print_section(college: College, tt: Timetable, section_id: str) -> None:
    sec = college.section(section_id)
    shift = college.shift(sec.shift_id)
    groups = {b.id for b in sec.batches}
    lunch = {ln.day: ln.period for ln in tt.lunches if ln.section_id == sec.id}
    width = 22
    print(f"\n{sec.name} ({shift.name} shift)")
    print("Period".ljust(13) + "".join(d.ljust(width) for d in college.days))
    for i, p in enumerate(shift.periods):
        row = f"{p.start}-{p.end}".ljust(13)
        for day in college.days:
            if lunch.get(day) == i:
                row += "LUNCH".ljust(width)
                continue
            cells = []
            for s in tt.sessions:
                if s.day != day or not (s.start_period <= i < s.start_period + s.length):
                    continue
                if section_id in s.section_ids and (s.batch_id is None or s.batch_id in groups):
                    code = college.subject(s.subject_id).code
                    tag = f"[{s.batch_id.split('-')[-1].upper()}]" if s.batch_id else ""
                    cells.append(f"{code}{tag}@{college.venue(s.venue_id).name}")
            row += (" / ".join(cells) or "-")[: width - 1].ljust(width)
        print(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default="cse-3a")
    ap.add_argument("--time", type=float, default=30.0)
    args = ap.parse_args()

    college = build_demo_college()
    print(f"{college.name}: {len(college.sections)} sections, {len(college.teachers)} teachers, "
          f"{len(college.venues)} venues, {len(college.allotments)} allotments")
    tt = generate(college, time_limit=args.time)
    print(f"Status: {tt.status} in {tt.solve_seconds}s, {len(tt.sessions)} sessions")
    for m in tt.messages:
        print(" -", m)
    for w in tt.warnings:
        print(" ~", w)
    if not tt.sessions:
        return

    violations = validate(college, tt.sessions, tt.lunches)
    print(f"Validator: {len(violations)} violation(s)")
    for v in violations[:20]:
        print(" !", v.message)

    print(f"Lunches: {len(tt.lunches)} (one per section per day, inside each mess window)")

    q = score(college, tt.sessions, tt.lunches)
    print(f"Quality score: {q.score}/100")
    for item in q.items:
        print(f"  - {item.label}: -{item.penalty} ({item.detail})")

    print_section(college, tt, args.section)


if __name__ == "__main__":
    main()
