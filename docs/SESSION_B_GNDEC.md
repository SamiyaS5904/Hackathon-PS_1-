# Session B, task 2: GNDEC dataset (realistic, re-engineered, made-up names)

> Given 2026-10-27. Session A (main checkout) builds the home page, README / docs and the deployment,
> then adds this college to the database and the Demo page ("compile"). Read `CLAUDE.md` first.

## Goal
A second demo college, **"Guru Nanak Dev Engineering College (demo)"** (short: GNDEC), realistic enough
to test the app and the assistant on real-life problems:
- students not knowing **where to sit in a free lecture** (free rooms now),
- **gaps** in the day, especially in final year,
- a lab (**JPAL**) that only **some** final-year CSE students attend,
- teacher leave and substitutes, makeup classes, room bookings.

Re-engineer it from GNDEC's own public pages: timetables, sections, subjects, rooms / labs and the
number of teachers. **Don't copy real people's names**: teachers and students get made-up, realistic Punjabi /
Indian names. Subjects, room names and lab names can follow the real ones. Aim to be *better* than the
real timetable (fewer gaps, every section gets lunch, no clashes), not a copy of it.

Sources to study (and every other department page linked from them):
- CSE: https://cse.gndec.ac.in/?q=node/5 (timetable page), and its infrastructure / faculty pages
- IT, Mechanical, Civil: each department's site (timetable, labs, lecture rooms, faculty count)
- First-year common subjects (Applied Sciences: maths, physics, chemistry, English, etc.)

## Deliverables (in this order, small tested commits on your own branch)
1. **Blank template**: `docs/demo-data/GNDEC/Timetabl_blank_template.xlsx`, the department Excel format
   (`backend/app/io/excel.py` `template()`), headings only, plus a "Read me" sheet explaining every column
   in plain words.
2. **Seed module** `backend/app/seed/gndec.py` with `build_gndec_college() -> College`, the whole college in
   one go (like `build_demo_college()` in `backend/app/seed/demo_college.py`):
   - Departments: CSE, IT, ME (Mechanical), CE (Civil), and Applied Sciences for first-year common teaching.
   - Years 1-4 for each of the 4 departments, real-life section counts / sizes (keep the total at about
     **28-40 sections**: the solver must stay fast on a laptop with little memory; see the note below).
   - GNDEC-like time grid (check the real period timings), the **flexible lunch** (mess window, one gap per
     section per day), no fixed breaks unless the real timetable has them.
   - Lab batches; first-year **combined / common** classes; **JPAL lab** as an elective group or pooled group
     with a **student-level list** (only some final-year CSE students); electives in final year.
   - Rooms and labs per department, plus shared halls, with realistic capacities and tags.
   - Teachers per department (made-up names), who-can-teach rows with 2+ teachers for most subjects, so the
     leave cover plan finds same-subject substitutes.
   - Students with made-up names, roll numbers and emails `<roll>@gndec.demo`.
   - Demo logins like the demo college: one Admin, one Coordinator per department, a few teachers and one
     student per section, all with password `demo1234`. Look at how `build_demo_college()` and the store /
     accounts seed the demo logins and copy that pattern (but **don't** write to the shared database).
3. The same data as **department Excel files** in `docs/demo-data/GNDEC/` (one per department, the upload
   format), so a new college can also be built by uploading them.
4. **Tests** `backend/tests/test_gndec_seed.py`: builds, feasibility pre-check passes, generates with
   **0 validator violations**, JPAL students only, every section gets lunch every day. Record solve time.
5. **Agentic test script** `docs/demo-data/GNDEC/assistant_scenarios.md`: 15-20 realistic questions per role
   (student: "where can I sit now?", "when is my JPAL lab?", "do I have gaps tomorrow?"; teacher; Coordinator:
   leave cover, moves, makeups; Admin) with what a good answer contains. If you can, run them against a local
   copy (SQLite, other ports) and note the results.

## Rules
- Don't touch the shared database in `backend/.env` (Supabase); use local SQLite for any manual test.
- Memory: the laptop has under 1 GB free. Run tests one file at a time with
  `SOLVER_WORKERS=2 OPENBLAS_NUM_THREADS=1`. If generation is slow, reduce sections rather than add memory.
- Don't edit the frontend, `chatbot/` or `backend/app/main.py`; Session A does the demo page and the loading.
- Plain wording (there is a banned-words test), Conventional Commits ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Don't push; Session A merges your branch.
- First bring your branch up to date with `main` (it has moved a lot: leave / substitutes, voice, router).

## Done when
All deliverables exist, `pytest tests/test_gndec_seed.py` passes, and you report: sections / students /
teachers / rooms counts, solve time, quality score, what is re-engineered from GNDEC, and anything not done.
