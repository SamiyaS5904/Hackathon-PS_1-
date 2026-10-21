# backend/CLAUDE.md: API, solver, validator

> Read the root [`CLAUDE.md`](../CLAUDE.md) first (product, roles, golden rules, V1 scope). This file covers the backend service.

## Purpose
The backend is the **only** place that:
- reads/writes college data (Supabase Postgres),
- enforces roles and tenant isolation (together with RLS),
- **generates** timetables (CP-SAT) and **repairs** them after edits (LNS),
- **validates** that nothing clashes,
- imports Excel and exports Excel/PDF,
- writes the audit log and sends notifications.

The chatbot and frontend are clients of this API. If a rule matters, it lives here.

## Stack
Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 (or supabase-py; decide at scaffold) · Google OR-Tools (CP-SAT) · openpyxl · PDF library (WeasyPrint or ReportLab; decide at scaffold) · Resend · pytest · ruff + black. Deploy on Render/Railway.

## Folder structure (planned)
```
backend/
├── app/
│   ├── main.py                FastAPI app, routers, CORS
│   ├── core/                  config, auth (JWT verify → user, org_id, role, dept), errors, logging
│   ├── models/                Pydantic schemas (API contracts = source of truth for TS types)
│   ├── db/                    DB session, repositories per table
│   ├── routers/               one file per resource (orgs, setup, venues, departments, sections, subjects,
│   │                          teachers, allotments, rules, timetables, sessions, overrides, changes,
│   │                          audit, notifications, imports, exports, insights)
│   ├── services/              business logic (permissions, proposals, approvals, notifications)
│   ├── solver/
│   │   ├── build_model.py     input snapshot → CP-SAT model
│   │   ├── constraints/       one module per hard rule family
│   │   ├── objective.py       soft rules + weights → quality score
│   │   ├── generate.py        full college-wide solve
│   │   ├── repair.py          LNS: freeze all but neighbourhood, minimise changes
│   │   ├── feasibility.py     pre-checks + infeasibility explanation
│   │   └── allotment.py       teacher allotment suggestion (if time)
│   ├── validator/             independent pure-function clash checker (no OR-Tools import!)
│   ├── io/                    excel_import.py, excel_export.py, pdf_export.py, templates/
│   └── notify/                in-app + email
├── supabase/
│   ├── migrations/            SQL schema + RLS policies (numbered, never edit an applied one)
│   └── seed/                  demo college (2 shifts, 4 depts, labs, electives, dummy student emails)
└── tests/                     pytest: validator, solver, repair, permissions, import
```

## Data model (all tenant tables have `org_id uuid not null` + RLS)
| Table | Key fields |
|---|---|
| `organizations` | name, slug, timezone, structure_levels (program/section/batch flags), shift_count |
| `memberships` | user_id, org_id, role (`admin`/`coordinator`/`teacher`/`student`), department_id? |
| `invites` | email, role, department_id, token, status |
| `shifts` | name, start_time, end_time |
| `time_grid` | working_days, lecture_minutes, lab_minutes (one value per college), periods per shift |
| `breaks` | shift_id, year_level_id? (null = all years), start_time, minutes, label |
| `holidays` / `semesters` | date, label / start_date, end_date (tentative, editable) |
| `programs`, `departments`, `year_levels` | hierarchy (program optional) |
| `sections` | department_id, year_level_id, name, strength, shift_id |
| `batches` | section_id, name, strength |
| `students` | user_id?, roll_no, name, email, section_id, batch_id?, elective choices |
| `teachers` | user_id?, name, email, departments[], shift_pref (`morning`/`evening`/`both`), max_per_day |
| `teacher_blocks` | teacher_id, day/date, slots, status (`confirmed` auto if clash-free) |
| `venues` | name, type, capacity, tags[], owner_department_id? (null = shared) |
| `subjects` | code, name, department_id, year_level_id, lecture_hours, tutorial_hours, lab_hours, lab_venue_tag? |
| `elective_slots` | name, section_ids[] (participating sections, can span departments), meetings_per_week |
| `elective_groups` | elective_slot_id, subject_id, teacher_id, venue requirement, member student_ids[] (from the student-level list) |
| `teacher_subjects` | teacher_id, subject_id, preference (1 = most wanted); entered by the Coordinator; drives allotment suggestions |
| `allotments` | subject_id, section_ids[] (combined) or batch_id, teacher_id, status (`suggested`/`approved`) |
| `department_status` | department_id, ready (bool), ready_at |
| `rules` | scope (`college`/`department`), department_id?, type, params (json), mode (`must`/`try`), weight, enabled |
| `timetables` | semester_id, version, status (`draft`/`published`), quality_score, generated_at |
| `sessions` | timetable_id, allotment_id, day, start_slot, length, venue_id, teacher_id, section_ids[]/batch_id, locked |
| `overrides` | session_id?, date, kind (`cancel`/`move`/`extra`/`substitute`), new day/slot/venue/teacher, reason |
| `change_proposals` | created_by, source (`manual`/`drag`/`chatbot`/`teacher`/`system`), diff (json), status, permanent (bool), needs_approval_by |
| `audit_log` | actor_id, action, entity, before (json), after (json), source, reason, reverted_by? |
| `notifications` | user_id, type, payload, read_at |
| `share_links` | section_id/teacher_id, token, active |
| _future_ `attendance_policies`, `attendance` | keyed by `occurrence_id` (= session_id + date). Do not build in V1, but keep IDs stable |

**RLS:** every policy checks `org_id = auth.jwt() ->> 'org_id'` (via a membership lookup); coordinators additionally limited to their `department_id` for writes; students read only their section's published data.

## Auth & permissions
- Verify the Supabase JWT on every request → `CurrentUser(user_id, org_id, role, department_id)`.
- **Never** accept `org_id` / role from the body or query.
- Permission checks live in `services/permissions.py` as small named functions (`can_edit_session(user, session)`, …) and are unit-tested. Matrix = root `CLAUDE.md` §4.
- The chatbot calls this API **with the end user's JWT**, so the same checks apply automatically.

## Solver specification (CP-SAT)

**Time model:** each shift has an ordered list of teaching slots per working day (breaks are not slots). A lecture = 1 slot; a lab = `lab_minutes / lecture_minutes` consecutive slots (must not cross a break).

**Decision variables:** for each required meeting `m` (from allotments × weekly hours) and each feasible (day, start_slot, venue): a boolean `x[m,d,s,v]`. Pre-filter domains aggressively (wrong venue type, capacity too small, wrong shift, teacher blocked, holiday-agnostic weekly template) to keep the model small. Optionally use interval variables + `AddNoOverlap` per teacher/venue/section.

**Hard constraints**
1. Each meeting scheduled exactly once.
2. No overlap per **teacher**, per **venue**, per **section** (and per **batch**; a section's whole-class meeting blocks all its batches).
3. Venue type matches (lab ↔ lab tag), capacity ≥ total strength (combined sections summed).
4. Section only inside its **shift** window (strict); teacher only in their allowed shift(s).
5. Labs = consecutive slots of the college lab length, within one block (no break inside). Batches of the same section may run different labs in parallel.
6. **Elective slots**: all groups of a slot meet at the same time(s), each in its own room with its own teacher (any department). Every participating section is blocked for the whole slot (no student is free; home sections don't meet). Each group's room must hold its member count. Pooled cross-department groups use the same mechanism.
7. Combined classes: all member sections free at that slot.
8. Teacher **block times** respected.
9. **Flexible lunch**: one period per (shift, year) inside the mess window, chosen by the solver; that year's students are free then every day.
10. Admin-fixed / locked sessions (common classes, manually pinned) are fixed.
11. Every enabled rule with mode `must`.

**Soft objective (minimise weighted penalties → quality score 0–100)**
- Teacher load: over `max_per_day`, > 3 consecutive periods, uneven spread across days.
- Students: idle gaps between classes in a day; same subject more than once a day (labs excepted).
- Venue fit: big hall for small class (wasted seats); prefer the department's own venues before shared/borrowed; **home room**: keep each section's lectures in as few rooms as possible.
- Every enabled rule with mode `try` × its weight.
Report each penalty component separately so the UI/chatbot can explain the score.

**Solve settings:** time limit (e.g. 30–60 s V1), multiple workers, return best found + status; run as a background job with progress polling (`/timetables/{id}/job`).

**Infeasibility:** run `feasibility.py` pre-checks first (hours needed vs slots available per section/teacher/venue type/shift). If CP-SAT still returns infeasible, re-solve with rule groups as assumptions to find the conflicting group, and return a plain-language explanation + suggested fixes.

## Repair (LNS) for edits
Input: current timetable + requested change (move/cancel/swap/teacher change/leave). Steps: pin the requested change → unfix only the affected neighbourhood (same teacher / section / venue on the affected days) → re-solve minimising **number of changed sessions** first, quality penalty second → if no solution, widen the neighbourhood once → else return "not possible" + reasons. Must be fast (< 2 s typical) because drag & drop and the chatbot depend on it.

## Validator
- Pure Python, **no OR-Tools import**, independent from the solver so it can catch solver bugs.
- Input: timetable (+ overrides for a date) + org data. Output: list of violations `{type, entities, day, slot, message}`.
- Checks every hard constraint above. Runs after generate, after repair, before apply, and in tests on every fixture.

## One-day overrides vs permanent changes
- **Weekly template** = `sessions`. **One-day** change = `overrides` row for a date. Effective timetable for a date = template ⊕ overrides ⊕ holidays.
- Teacher one-day change: validate → apply instantly → notify Coordinator + affected students.
- Teacher permanent change: create `change_proposal` with `needs_approval_by = coordinator` → apply on approval.
- Everything goes through `services/proposals.py`: create → validate → (approve) → apply → audit → notify.

## Import / export
- Excel template workbook (sheets: Venues, Sections, Students, Teachers, Subjects, Allotment) with example rows + dropdown validation, downloadable from the API.
- Import = parse → validate rows → return preview with **row-level errors** → commit only on confirm. Idempotent on natural keys (venue name, section name, subject code, email).
- Export: Excel and PDF per section / teacher / venue and a master college sheet; respects published version.

## API conventions
- REST, JSON, plural nouns: `/orgs/{org}/sections`, `/timetables/{id}/generate`, `/proposals/{id}/apply`.
- Errors: `{error: {code, message, details}}` with proper HTTP status; messages are user-friendly.
- All list endpoints paginate; all writes return the updated resource.
- OpenAPI schema is consumed by the frontend type generator; keep models documented.

## Testing (pytest)
- Validator: hand-made clash fixtures, each must be detected.
- Solver: small/medium synthetic colleges (1 and 2 shifts, labs + batches, electives, combined classes) → result must have **zero validator violations**; infeasible fixtures must return an explanation.
- Repair: change applied, nothing else moved unnecessarily, still valid.
- Permissions: each matrix row has a test (allowed and denied).
- Import: bad rows produce exact row-level errors.

## Definition of done (backend)
Endpoint protected by auth + permission check · RLS policy exists for any new table · validator passes · tests added and green · OpenAPI updated · committed.

## Commands
_Fill in after scaffolding:_ `uvicorn app.main:app --reload` · `pytest` · `ruff check . && black --check .` · `supabase db push` / migration command
