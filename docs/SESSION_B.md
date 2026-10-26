# Session B: app features (prompt for a parallel Claude Code session)

> Session B is **already running** in the Claude app (its own worktree, branch `session-b-features`).
> Use this file only if you start it again in another chat: paste everything below the line.

---

You are **Session B** of Timetabl.ai. Read `CLAUDE.md` (root), `backend/CLAUDE.md` and `frontend/CLAUDE.md` first.
The hackathon submission is tomorrow (2026-10-27). Another session (**Session A**) works in parallel in the main checkout on:
- the agentic assistant, voice and talk mode, the cost card;
- teacher leave + substitutes, shown as a plan card on the Coordinator Home.

You do the **app features** below.

## Rules
- No clash ever reaches a user: run the validator on every change. Every change is audited and notified. Tenant isolation everywhere.
- Plain college wording in the UI. `backend/tests/test_wording.py` bans jargon. Do **not** redesign the visual theme.
- The database in `backend/.env` is shared with Session A and holds only the Demo Institute (org `demo`, Dr. Anita).
  Never delete or reseed it, and never print secrets.
- Work on your own branch with small tested commits (Conventional Commits). End every message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Don't push and don't merge into `main`.

## How to avoid clashing with Session A
- New backend endpoints go in **new router files**, included in `backend/app/main.py` with one line each.
- Append new types and functions at the **end** of `frontend/lib/types.ts` and `frontend/lib/api.ts`.
- Don't edit these:
  - `chatbot/`
  - `frontend/components/chat/*`
  - `frontend/components/home/StaffHome.tsx`
  - `backend/app/edits/oneday.py`, beyond a small venue-event check
- For browser checks, use ports 8100 (backend), 8101 (assistant) and 3100 (web).

## Tasks (in order)
1. **Teacher–student slot booking.**
   - Test it end to end on the demo college: the teacher sets office hours → the student books a doubt slot → both see it and get notified. Also test the Coordinator's meeting finder.
   - Fix any bug.
   - Make *Bookings* easy to find for teachers and students (a main nav item in `frontend/components/layout/AppShell.tsx`).
2. **Teacher reschedule finder.**
   - A teacher finds a time when they, their students and a room are all free.
   - They move the lecture for one day, or ask to move it for good.
   - Students get notified.
   - Keep it to 3 clicks or fewer.
3. **Venue booking for events** (new).
   - Any teacher picks a date and start/end period and sees the list of venues free then. "Free" means no class, no one-day change, no other approved event, and not a holiday.
   - They book a venue with a reason and a club name.
   - The Coordinator of the venue's department approves or declines (the College Admin for shared venues), and the requester is notified.
   - An approved event holds the room for that date, so one-day moves, makeups and other events can't take it.
   - It only uses free rooms and never bumps a class.
   - Build it with a new router file, its own table (with `org_id`) and a new page reachable by teachers, Coordinators and the Admin.
   - Add tests, including role and college isolation.
4. **Mess split as a Try rule.**
   - The flexible lunch spreads students evenly over the periods in the mess window, weighted by section strength. For example, half the students at 11:30 and half at 12:30.
   - It can be turned on or off on the Rules page.
   - The demo still generates with 0 violations.
5. **3–4 more demo teachers** with real-looking Indian names, added in `backend/app/seed/demo_college.py` with their who-can-teach rows.
   - The demo still generates with 0 clashes and the tests stay green.
   - Don't reseed the live database; tell the user what would change.
6. If time is left: **notices** from Coordinators and the Admin.
   - Text, an audience (department teachers / department students / a year / a section), and an expiry date.
   - Shown on Home and in the bell.

## Done when
- Each item works on the demo college.
- `cd backend && pytest` and `cd chatbot && pytest` are green.
- `npx tsc --noEmit` and `next lint` are clean.
- Then a short report: the commits, and anything not done.
