# CLAUDE.md — Timetabl.ai

> Read this file first, every session. It is the single source of truth for **what** we are building and **how** we work.
> Each sub-folder has its own `CLAUDE.md` with the details for that part:
> [`frontend/CLAUDE.md`](frontend/CLAUDE.md) · [`backend/CLAUDE.md`](backend/CLAUDE.md) · [`chatbot/CLAUDE.md`](chatbot/CLAUDE.md)

---

## 1. What we are building

**Timetabl.ai** is a multi-tenant SaaS that builds **clash-free college timetables** for *any* college and keeps them right all semester.
A college signs up, answers a guided setup (shifts, periods, breaks, venues, departments), Department Coordinators fill their department's data, and the College Admin generates a college-wide timetable with one click. After publishing, changes (moves, cancellations, leaves, one-day reschedules) go through a safe *repair → validate → preview → apply* pipeline, and a role-aware **AI chatbot** answers questions and makes edits.

**Hackathon judging criteria → how we win each one**

| Criterion | Our answer |
|---|---|
| Core functionality: no clashes | CP-SAT solver with hard constraints + an **independent validator** run on every timetable and every edit |
| Usability: admin without help | Step-by-step setup wizard, Excel import with row-level errors, demo college, empty states that say what to do next |
| Design: clear, readable | Clean Linear/Notion-style UI, colour-coded grids, section / teacher / room views, light + dark |
| Advanced functionality | 2 shifts, shared rooms across departments, combined classes, parallel electives, lab batches, one-day overrides, agentic chatbot |
| Relevance | Real college workflows: Coordinator approval, teacher leave + substitutes, notifications, audit log, PDF/Excel for notice boards |

**Timeline:** hackathon, 1–3 days, solo developer working with Claude Code. **Ship V1 first, perfectly.** V2 is the roadmap.

---

## 2. Golden rules (never break these)

1. **No clash ever reaches a user.** Every generated or edited timetable passes `backend/validator` before it is saved or shown as a proposal.
2. **Timetable generation uses the algorithm, never an LLM.** Claude powers only the chatbot.
3. **The chatbot never writes directly.** It creates a `ChangeProposal`; the user sees a before/after diff and clicks Apply.
4. **The chatbot acts with the logged-in user's permissions.** It calls the backend with the user's own token; it can never do more than the user could do by hand.
5. **Tenant isolation:** every tenant table has `org_id`; the backend is the only database client and checks the caller's membership on every `/api/orgs/{org}` request (org from the URL, user from the signed token, role from the database: **never from the request body**). A college you're not in answers 404, exactly like one that doesn't exist.
6. **Every change is logged** (who, what, when, how: manual / drag / chatbot / system, reason) and can be undone.
7. **Configurable, not hard-coded.** Anything that differs between colleges (shifts, periods, breaks, lab length, rules, structure levels) is data, not code.
8. **Small working commits** after every step (see §10). Never leave `main` broken.
9. **Ask the user before big decisions** (architecture, new dependencies, scope changes). Explain options in plain language; the user prefers numbered plain-text questions.
10. Terminology: the department-level role is **Department Coordinator** (never "HOD").
11. **Core first (80/20), see §2A.** The core loop gets the prime place in the UI and the first share of build time. Secondary features never crowd it out.

---

## 2A. Core vs secondary (80/20): placement rule

**~80% of the value is the core loop: set up data → generate a clash-free timetable → view it → change it safely.**
Everything else is secondary. This decides **where a feature lives in the UI** and **what gets built and polished first**.

| | Core (prime placement) | Secondary (one level down) |
|---|---|---|
| **Features** | Setup data (wizard / Excel), **Generate**, timetable grid (section / teacher / venue), drag & drop + clash check, one-day changes, publish | Chatbot panel, insights, notifications, audit log, exports, rules page, approvals inbox, TV board, reports |
| **UI placement** | Main sidebar items + the **one primary button** on each screen (e.g. *Generate*, *Publish*, *Apply*). Dashboard top = "next step" card + timetable health | Toolbar icons, side panel (chat), bell (notifications), "More" menus, settings pages, secondary buttons |
| **Build order** | Built first, works end-to-end before anything secondary starts | Built only after the core loop works on the demo college |
| **Polish** | Empty / loading / error states, keyboard use, mobile view: always | Good enough first, polished if time |

Rules of thumb:
- **One primary action per screen**, and it is always a core action. Secondary actions use secondary button styles.
- The timetable grid is the hero: it gets the most screen space; panels (chat, details) slide over or beside it and never replace it.
- A secondary feature may *point to* the core (chat proposes a change → user applies it in the grid) but never duplicates or hides it.
- If time runs short, cut from the secondary column, never from the core.

---

## 3. Repository map

```
/
├── CLAUDE.md            ← you are here (product + rules)
├── frontend/            Next.js web app (all screens for all roles)
│   └── CLAUDE.md
├── backend/             FastAPI: data API, solver, validator, import/export, notifications, DB migrations
│   └── CLAUDE.md
└── chatbot/             FastAPI agent service: Claude tool-use loop, calls backend with the user's token
    └── CLAUDE.md
```

```
 Browser ──► frontend (Next.js, Vercel)
                │  REST (Supabase JWT)          │  SSE stream (Supabase JWT)
                ▼                               ▼
          backend (FastAPI)  ◄──── REST ────  chatbot (FastAPI + Claude API)
           solver · validator · io · notify     tools = backend endpoints
                │
                ▼
          Supabase (Postgres + Auth + RLS)  ·  Email (Resend)
```

---

## 4. Users & roles

Hierarchy: **Super Admin (platform)** → **College Admin** → **Department Coordinator** → **Teacher** → **Student**.

| Action | College Admin | Dept Coordinator | Teacher | Student |
|---|---|---|---|---|
| College setup (structure levels, shifts, periods, breaks, holidays, semester dates) | ✅ | ❌ | ❌ | ❌ |
| Invite Coordinators | ✅ | ❌ | ❌ | ❌ |
| Invite teachers | ✅ | ✅ own dept | ❌ | ❌ |
| Shared venues, common / cross-dept classes (Admin owns them) | ✅ | view | ❌ | ❌ |
| Dept venues, sections, subjects, student lists | ✅ | ✅ own dept | ❌ | ❌ |
| Teacher allotment (system suggests → Coordinator approves) | ✅ | ✅ own dept | ❌ | ❌ |
| Mark department data **Ready** | — | ✅ | ❌ | ❌ |
| College-level rules / dept-level rules | ✅ / ✅ | — / ✅ own dept | ❌ | ❌ |
| Generate college-wide timetable, publish | ✅ | ❌ | ❌ | ❌ |
| Reschedule / cancel / reassign lectures | ✅ all | ✅ own dept | own lectures only | ❌ |
| Teacher **one-day** change | — | notified | **instant** if clash-free | notified |
| Teacher **permanent** change | — | **approves** | requests | notified |
| Teacher block time | — | notified | **auto-confirmed** if clash-free | ❌ |
| Use another dept's free room | ✅ | ✅ first-come, owner notified | via own changes | ❌ |
| Teacher leave → substitute | ✅ | picks from ranked suggestions | marks leave | notified |
| Undo from audit log | ✅ | ✅ own dept | ❌ | ❌ |
| View | everything | own dept + shared | **own lectures only** | own section / electives |
| Chatbot | full | own dept | own lectures | **read-only**, own schedule + free rooms / where-is |

**Super Admin** manages tenants (colleges) and platform health; never edits college data.

**Accounts:** college creator becomes College Admin (self-signup + one-click demo college). Staff join by **email invite** (magic link) with role + department pre-assigned. Students use **light login**. V1: simple email + password with dummy college emails (seeded per section for the demo college, or created from the uploaded student list), already linked to their section/batch/electives. V2: Google / real college email sign-in. A public read-only link per section also exists.

---

## 5. Domain glossary

| Term | Meaning |
|---|---|
| Organization (org) | One college = one tenant |
| Structure levels | Configurable per college: **Program → Department → Year/Semester → Section → Lab batch** (Program, Section, Batch optional) |
| Shift | 1 or 2 per college (morning / evening). Sections belong strictly to one shift. Teachers are Morning / Evening / Both. Venues are reused across shifts |
| Time grid | Working days, shift timings, lecture duration, **one lab duration for the whole college**, fixed breaks, and a **flexible lunch**: admin gives the mess window per shift; the solver gives **every section one free period inside it, every day**, chosen per section and per day (it may differ from day to day) for the best timetable and venue use |
| Venue | Room with type (lecture hall / lab / seminar / auditorium), capacity, tags, owner dept or *Shared* |
| Section | A group of students that always sits together (atomic). Room capacity ≥ strength |
| Lab batch | Sub-group of a section for labs (A1/A2), runs in parallel |
| Subject | Code, dept, year, lecture/tutorial/lab hours per week |
| Allotment | Subject + section(s)/batch + teacher. Several sections = combined class |
| Elective slot | A fixed time when **every student of the participating sections** (e.g. all final-year sections of 5 departments) is in one of the slot's elective groups. Home sections don't meet then. All groups of a slot run at the **same time**, each with its own teacher and room (any department). Membership comes from the student-level list |
| Elective / pooled group | One option inside an elective slot (ML / Cloud / IoT), or a **pooled class**: students from several departments taught together by another department's teacher in that department's room. Room capacity = number of members |
| Session | One scheduled class in the **weekly template** (slot, venue, teacher, section/batch) |
| Override | A **date-specific** change on top of the template (reschedule / cancel / extra class) |
| Occurrence | Template session ⊕ overrides on a real date; has a stable `occurrence_id` (future attendance hooks onto it) |
| Rule | A constraint card: on/off, **Must** (hard) or **Try** (soft, weighted); college-level or dept-level |
| Change proposal | A set of session/override changes + diff, waiting for Apply/Discard |
| Quality score | 0–100 from soft rules: teacher load balance, student gaps, same subject ≤1/day, room-size fit |

---

## 6. Core flows

**Semester flow**
1. Admin signs up → setup wizard: *How many shifts?* (1 → normal; 2 → timings for each + how students are divided: by year / dept / section, day scholar vs hosteller → section table with Morning/Evening toggle) → lecture & lab duration → breaks per year → holidays upload → tentative semester dates.
2. Admin adds venues, departments, rules; invites Coordinators.
3. Coordinators add sections, students, subjects, teachers (wizard or Excel) → system suggests teacher allotment → Coordinator approves → marks **Ready**.
4. Admin sees department readiness checklist → **Generate** (college-wide CP-SAT) → validator → quality score + insights.
5. Admin reviews → **Publish** → everyone notified; Excel/PDF ready.
6. Daily life: one-day changes, leaves & substitutes, makeup classes, chatbot, Now & Next board.

**Change flow (every edit, from any source)**
Drag & drop / chatbot / teacher request / leave → **solver repair** (freeze everything else, minimise changes) → **validator** → **preview + permission check** (permanent teacher change → Coordinator) → **apply** → audit log + notifications + undo.

---

## 7. Scheduling model (summary; full spec in `backend/CLAUDE.md`)

- **Algorithm:** Google OR-Tools **CP-SAT** for generation; **LNS repair** (re-solve a small neighbourhood with everything else fixed, minimise number of changes) for edits; **independent validator** after both.
- **Hard:** no teacher / venue / section / batch double-booking (also across overlapping shifts); venue type + capacity; shift windows (strict); breaks & holidays; flexible lunch (every section, every day, a free period inside the mess window); teacher block times + daily limit; labs as consecutive blocks of the college lab length, batches in parallel; same subject at most once a day; combined classes & elective groups together; all *Must* rules.
- **Soft (quality score):** compact student days (few gaps), balanced teacher load, right-sized rooms, **home room** (few room changes per section), own department's rooms before borrowed ones, all *Try* rules with weights. Goal: highest quality and most efficient venue use.
- Infeasible input → explain which rule group conflicts in plain language (never a silent failure).

---

## 7A. Edge cases checklist

Every feature must keep these in mind. ✅ = handled + tested in the engine · 🔜 = planned (stage in brackets). Add new cases here when found.

**Students & sections**
- ✅ A department has **more students than its own rooms can hold** → lectures automatically use shared rooms or other departments' free rooms (first-come); admin gets a warning with the hours that will be borrowed.
- ✅ A section is **bigger than every room its department owns** → uses a bigger shared/other room; warning shown.
- ✅ A section is **bigger than every room in the college** → blocking error with the fix (split the section or add a hall).
- ✅ Students of one department **taught in another department's rooms or by another department's teachers** (e.g. first-year common subjects).
- ✅ **Combined classes** across departments need a room for the total strength; combined sections in different shifts → error.
- ✅ Lab batches whose strengths don't add up to the section; batch bigger than every suitable lab → error.
- ✅ **Elective slots** across departments: CSE students in a group taught by an ME teacher in an ME room; all groups of a slot at the same time; home sections blocked; room fits members, not sections.
- ✅ **Pooled groups**: a few students from several departments taught together in another department (same mechanism).
- ✅ Student-level lists: every student of a participating section must be in exactly one group of each elective slot; missing or double-assigned students → plain-language error naming the roll numbers.
- ✅ Auto-sectioning a whole-year list that doesn't divide evenly: sizes differ by at most one; batches too.
- ✅ A damaged Excel file gets a plain message, never a server error.

**Rooms**
- ✅ **Not enough big-enough room time college-wide** (checked per group size: 120+, 60+, ...) → error before solving.
- ✅ No lab with the required equipment tag → error.
- ✅ The same room used by two shifts whose timings overlap.
- 🔜 Room temporarily unavailable (maintenance, exams) (3).

**Teachers**
- ✅ Teacher block times confirmed instantly only if they don't clash with current lectures.
- ✅ Teacher in two departments or both shifts; overlapping shift times checked.
- ✅ Weekly load above `max_per_day × days` → error; blocked times respected.
- ✅ Classes without a teacher block generation with a clear message; suggestions fill them within weekly limits.
- 🔜 Teacher on leave → substitutes (if time); teacher leaves mid-semester → re-allotment (V2).

**Time**
- ✅ Lab can't cross a break; mess window without a full period → error; more weekly lectures than working days → error.
- ✅ Holidays (no classes that day; one-day moves onto them refused) and one-day overrides on real dates; semester dates editable in setup.

**Data & scale**
- ✅ Unknown references (section, teacher, subject, shift) → error naming the row.
- ✅ Duplicate names / codes / emails in Excel import → row-level errors; re-import keeps ids (sections, teachers, subjects, rooms, students).
- 🔜 Large colleges (50+ sections): solve time grows; plan: progress bar + time limit, then solve per shift / per year with shared rooms fixed (later).

---

## 8. Feature status

> V1/V2 board confirmed 2026-10-21; updated 2026-10-25 after the V1 audit. ✅ done (works end-to-end on the demo
> college, tested) · 🔨 building now (in this order) · 🔭 future.

**✅ Done: V1 (stages 1–7, deploy pending)**
- **Accounts:** self-signup creates a college (creator = College Admin); demo page with one-click login per role; email invites with role + department (Admin → Coordinators/teachers, Coordinator → own teachers); **student login with demo emails** (`cse3a.01@demo.timetabl.ai`, password `demo1234`; new colleges: from the student list, first password = roll number)
- **Tenant isolation:** every `/api/orgs/{org}` request checks membership; another college answers 404
- **Setup wizard:** 1 or 2 shifts (strict), periods per shift, one lab length, **flexible lunch** (mess window per shift; every section gets one free period inside it every day, chosen per section per day), holidays, semester dates, departments, shared rooms; *Load sample college* for a brand-new college
- **Department data:** sections, batches, subjects, teachers, who-can-teach, classes, students, rooms; Excel template (pre-filled, example rows for an empty department) → upload → row-level errors → save; re-import keeps ids
- **Fair teacher suggestions** (busiest teacher as light as possible, nobody who can help left idle, preferences, same teacher for a section's lecture + lab) → Coordinator approves
- **Ready flow:** Coordinator marks Ready (only once sections, classes and teachers exist); Admin sees the readiness checklist
- **Generation:** CP-SAT college-wide, labs as blocks with parallel batches, combined classes, elective slots + pooled cross-department groups, shared/borrowed rooms, home room, teacher block times, rules (Must/Try); feasibility pre-check in plain language; **independent validator** on every timetable and every change; quality score
- **Views:** section / teacher / room, colour-coded, light + dark, phone widths; *Today* (now / next, countdown, room, lunch, greyed done classes) and *This week* (real dates) for teachers and students; teachers see only their own lectures, Coordinators only their department
- **Publish:** draft vs published; teachers/students keep the published one while a new draft waits
- **Changes:** drag & drop with green / amber / red slots → solver repair → diff → Apply; one-day cancel / move; **makeup class finder** (next 7 days, teacher + students + room free); teacher one-day change instant, permanent change = request → Coordinator reviews and applies; teacher block times auto-confirmed if clash-free; audit log with undo
- **Attendance portal** (separate from the timetable): teacher marks a class (everyone present by default, last 7 days editable); student *My attendance* (overall + per subject vs the college rule, "can miss N / attend next M"); Coordinator/Admin per section, below-rule students first; rule set by the Admin
- **Notifications:** in-app bell, audience-based (changed classes reach the students, teacher and Coordinator involved), only after publishing
- **Exports:** Excel + PDF per section / teacher / room, one or all
- **AI assistant** (side panel, Ctrl+K, role-scoped tools with the user's own token): Q&A, free rooms / free times, attendance questions, makeup times, bookings, edits as proposals with a diff (person clicks Apply), proactive suggestions after generation
- **Voice + language** (2026-10-25): replies mirror the user's language (English → English, Roman Hinglish → Roman Hinglish, never Devanagari), typed or spoken; mic with live transcript, auto-send after a pause, answers to spoken questions read aloud (toggle + stop), plain messages for a blocked / missing mic
- **Auto-sectioning** (2026-10-25): upload a whole-year list (roll no, name, email + any columns) → balanced sections (by roll number, or mixed evenly by a column such as Hostel) + lab batches, room / lab size warnings, preview, save; re-sectioning keeps section ids by name and student ids by roll / email, and never drops a section that still has classes
- **Minimal-change regenerate** (2026-10-25): *Regenerate → Keep the current timetable* makes every class leaving its day/time expensive for the solver, so only classes that must move do (demo: one new block time → 237 of 238 stay, 1 moves, 0 clashes, ~4 s; a fresh regenerate keeps only 17 in place); classes keep their ids (attendance stays attached); one-day changes carry over when they still fit; a summary banner says what moved. *Start fresh* is still there for before the semester
- **Super Admin platform** (2026-10-25): platform owners (`SUPERADMIN_EMAILS`, plus a demo owner `owner@demo.timetabl.ai` while `DEMO_PLATFORM_OWNER=1`) see every college: stage (Setting up → Live), size, adoption (accounts, attendance, bookings), health flags ("signed up but no setup", "draft not published", "no activity"), plans; they set plan / read-only / paused (enforced on every college request) and a private note, never college data (they aren't members, so college endpoints stay 404); a platform assistant answers in English or Hinglish and prepares plan / status changes as cards
- **Teacher booking** (2026-10-25): teachers set weekly office hours (seats, place; never on their own classes); students book doubt slots over the next 2 weeks (teacher free that day, seats left, no class for the student, no holiday); Coordinator (own department) / Admin find times when chosen teachers are all free and book meetings; notifications; a class later moved onto a booking is flagged with "Find another time"; the assistant finds slots and prepares bookings as cards

**✅ Done 2026-10-25:** voice + language quality · teacher booking · auto-sectioning · Super Admin platform · mid-semester regenerate with minimal change

**✅ Done 2026-10-27 (both sessions, merged into main):** teacher leave → cover plan (substitutes ranked, per year cancel / cover, Apply → validated one-day changes, undo, notifications; Coordinator Home + assistant card; teacher "Ask for leave") · assistant: parallel tools, leave / undo / show-on-screen tools, drives the screen, suggestions while typing · voice: Whisper (gpt-4o-transcribe) + natural TTS with `OPENAI_API_KEY` (or OpenRouter), browser voice fallback, Chat / Talk modes, interrupt by speaking · tomorrow's brief · assistant cost card (Admin + platform) · Session B: bookings in the main menu, reschedule finder, venue booking for events, mess split Try rule, 4 more demo teachers (seed only; live DB not reseeded), notices. Still to check by hand: microphone + cloud voice with a real key.

**✅ Done 2026-10-27 (later):**
- **Assistant:** model router (Sonnet 5.5 agentic, Haiku 5.5 look-ups, Opus 5.5 retry), instant answers without AI,
  English-first replies, roughly 2x faster.
- **Home page:** public `/welcome` with features and indicative pricing.
- **Deployment set-up:** Hugging Face Space for backend + assistant, Vercel, Supabase (`docs/DEPLOY.md`).
- **GNDEC (demo):** a second demo college (`backend/app/seed/gndec.py`), seeded at start-up (`DEMO_GNDEC`), with
  its own Demo page tab. It has 28 sections, 570 classes, 0 clashes and quality 79, plus a JPAL lab for selected
  final-year CSE students.

**Plan as built (2026-10-26)**
Data: only the Demo Institute (Dr. Anita) stays in the database; the GNDEC demo college comes later from the user's data (then also on the Demo page). Fixed breaks are optional (a new college has none).

*Session A: agentic assistant + teacher leave* (chatbot, leave/substitute backend, coordinator Home, chat panel)
1. **Teacher leave → plan card.** Teacher asks for leave (app or assistant) → Coordinator approves (or enters it directly, e.g. by voice: "Dr. Rita Arora is away 3 days; free the 4th-year lectures, substitutes for 3rd year"). The system builds a plan per class: *substitute* (a teacher who can teach the same subject, free then, within daily limits, ranked) or *cancel*, chosen per year. Plan card on the **Coordinator Home**: ticks per class → Apply (validator → one-day changes, new kind "substitute" → audit + undo → notifications to the students and teachers involved).
2. **Fast assistant, full quality:** Opus 5.5 kept (no low thinking); speed from prompt caching, compound tools that do several steps in one call, parallel tool calls, streaming the reply into speech sentence by sentence.
3. **Voice:** OpenAI Whisper for listening and OpenAI TTS for a natural voice (`OPENAI_API_KEY` in `chatbot/.env`, browser voice as fallback). Pause = keep listening; "Stop" stops listening/speaking and leaves the text editable (never auto-sent); speaking over it interrupts it.
4. **Two modes:** *Chat* (type or speak) and *Work with assistant* (hands-free talk mode): it talks, shows option cards to tap, and **drives the screen** (opens the timetable / teacher / section it talks about, highlights classes) while working.
5. Suggestions while typing · undo by voice · **evening brief the day before** for Coordinators (tomorrow's leaves, uncovered classes, "fix them?").
6. **Assistant cost card:** token use and $ per college (College Admin: own college; Super Admin: all).

*Session B: app features* (own worktree; new endpoints in new router files)
1. Test teacher–student slot booking end to end, fix what's broken, make *Bookings* easy to find for teachers and students.
2. Teacher reschedule finder done properly: "when are I, my students and a room all free" → move (one day / request for good) → students notified.
3. **Venue booking for events:** a teacher picks date + time, sees the list of venues free then, books with reason + club → Coordinator of the room's department approves (Admin for shared rooms) → the room is held for that date (classes, one-day moves and other events can't take it) → requester notified. Free rooms only, never bumps a class.
4. **Mess split as a Try rule:** lunch gaps spread evenly across the mess window (e.g. half the students at 11:30, half at 12:30).
5. 3–4 more demo teachers with real-looking names (demo still generates with 0 clashes).
6. If time: **Coordinator / Admin notices** (text, audience: department teachers / students / a year / a section, expiry) on Home + bell.

**🔭 Future (pitch roadmap, not building now)**
Calendar invites (`.ics`) / Google Calendar sync · WhatsApp / SMS notifications · email notifications (Resend) · QR posters · attendance extras (QR / self check-in, alerts below the rule, parent view) · substitutes on leave · Now & Next TV board · Google login for students · OpenAI Whisper as a second voice option · NAAC/NBA workload report · plain-language rules via the assistant · timetable version compare · room maintenance / exam blocks · solve per shift / year for 50+ sections

---

## 9. Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript strict, Tailwind, shadcn/ui, TanStack Query, dnd-kit → Vercel |
| Backend | Python 3.12, FastAPI, Pydantic v2, OR-Tools CP-SAT, openpyxl, a PDF library → Render/Railway |
| Chatbot | Python 3.12, FastAPI, Anthropic SDK (Claude tool use), SSE streaming → Render/Railway |
| Data / Auth | **Supabase Postgres** as the database (`DATABASE_URL`; SQLite file locally). Login, roles and invite links are handled by our backend (scrypt password hashes, signed JWT). Decided 2026-10-21: option B, one place for every permission rule, testable offline |
| Email | Resend |
| LLM model | Assistant router (decided 2026-10-27, measured on the demo college): **`claude-sonnet-5-5`** for agentic work (moves, leave cover, makeups, meetings, explanations; adaptive thinking, effort `medium`), **`claude-haiku-5-5`** for plain look-ups (schedule, free rooms, where-is, show on screen, undo), **`claude-opus-5-5`** once as a retry when a turn fails with an API error. Server-side refusal fallbacks `fallbacks: "default"`. Settings: `CHAT_MODEL`, `CHAT_FAST_MODEL`, `CHAT_RETRY_MODEL`, `CHAT_EFFORT`. Generation never uses an LLM |

**Environment variables** (never commit values; keep `.env.example` files current)
`DATABASE_URL` (Supabase Postgres; empty = local SQLite), `APP_SECRET` (signs login tokens), `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (optional, backend only), `ANTHROPIC_API_KEY` (chatbot only), `OPENAI_API_KEY` (chatbot, V2 Whisper), `RESEND_API_KEY`, `BACKEND_URL`, `CHATBOT_URL`, `NEXT_PUBLIC_*` for public frontend values.

---

## 10. How we work

**Git**
- Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:` with a scope, e.g. `feat(solver): add lab block constraint`.
- Commit after **every** small working step; push often. One feature = several small commits, never one giant commit.
- End every commit message with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Never commit secrets, `.env`, `node_modules`, `.venv`, build output.

**Definition of done (every feature)**
1. Works end-to-end on the demo college.
2. Validator passes on any timetable it touches; `pytest` green.
3. Reachable from the UI by the right role (and blocked for the wrong role).
4. Empty, loading and error states handled.
5. Committed with a clear message.

**Code conventions**
- Shared contracts: Pydantic models in `backend` are the source of truth; TypeScript types are generated/mirrored from the backend OpenAPI schema.
- Python: ruff + black, type hints everywhere. TypeScript: strict, ESLint + Prettier.
- Names in code use the glossary terms above (`venue`, `section`, `batch`, `session`, `override`, `coordinator`).
- Times are stored as slot indices + the org's time grid; dates in the org's timezone.

**Build stages** (simple MVP first, then grow; each stage ends in a working, committed state)

| Stage | Goal | Done when |
|---|---|---|
| **1. Engine** | `backend/`: domain models, demo college, CP-SAT generator, independent validator, quality score, feasibility pre-check, CLI, pytest. No DB, no UI | `pytest` green; demo college generates with **0 violations** |
| **2. See it** | FastAPI endpoints (in-memory store) + Next.js grid: section / teacher / venue views, Generate button | Open browser → click Generate → readable clash-free timetable |
| **3. Edit it** | Drag & drop with live clash check, LNS repair, diff preview, one-day overrides, audit log + undo | Move a class in the UI; nothing else breaks |
| **4. Real SaaS** | Supabase DB + RLS, auth, roles, invites, student dummy-email login, multi-college | Two colleges isolated; each role sees only its part |
| **5. Set it up** | Setup wizard (shifts, periods, breaks, holidays), Excel import, Coordinator Ready flow, rules page, electives, teacher block times | A new college goes from signup to timetable without help |
| **6. Chatbot** | Agent service: role-scoped Q&A, edits via proposals, proactive insights | "Move CSE-3A DBMS to Friday" works with a diff |
| **7. Ship** | Publish, Excel/PDF export, in-app notifications, approvals, polish, deploy | Live URL with the demo college |
| 8. Grow | §8 *Building now* list, in order | Each item works end-to-end on the demo college |

---

## 11. Commands

_To be filled in when each part is scaffolded._

| Task | Command |
|---|---|
| Frontend dev | `cd frontend && npm run dev` |
| Backend dev | `cd backend && uvicorn app.main:app --reload` |
| Chatbot dev | `cd chatbot && uvicorn app.main:app --reload --port 8001` |
| Backend tests | `cd backend && pytest` |
