# Timetabl.ai: timetables that never clash

**Clash-free college timetables in one click, and an AI assistant you can talk to that keeps them right all
semester.** Departments fill in their data, the College Admin clicks **Generate**, and every section, teacher and
room gets a timetable with **0 clashes**. When a teacher is away or a class has to move, the assistant plans the fix
and a person applies it with one click.

**Hackathon submission · Samiya Sehgal (URN 2302662) · Guru Nanak Dev Engineering College**

| | |
|---|---|
| **Live app** | **https://timetabl-ai.vercel.app** → *Explore the live demo* (one-click logins, password `demo1234`) |
| **Presentation** | [`Timetabl_ai_Hackathon_Submission.pdf`](Timetabl_ai_Hackathon_Submission.pdf) (20 slides) |
| **Testing datasets** | [`docs/demo-data/`](docs/demo-data/): GNDEC and PIET Excel files + a blank template |
| **Guides** | [Demo guide](docs/DEMO_GUIDE.md) · [Deploy guide](docs/DEPLOY.md) · [Design and rules](CLAUDE.md) |
| **API** | https://timetabl-api.fly.dev/api/health |

![Timetabl.ai home page](docs/screenshots/landing_hero.png)

---

## The problem → our solution

| The problem today | With Timetabl.ai |
|---|---|
| Two classes in one room, a teacher in two places | **0 clashes:** built by an algorithm (Google OR-Tools CP-SAT), checked by a separate validator |
| Weeks of manual work every semester | **One Excel sheet** per department, **one click** for the whole college |
| A teacher is away and classes simply vanish | **A cover plan in seconds:** ranked substitutes for every class |
| Every change means ten phone calls | **Ask the assistant** by voice or text; suggested slots; only the people affected are notified |

## Who uses it

```mermaid
flowchart TD
    P["Platform owner (Super Admin)<br/>plans, health, pause · never sees college data"]
    P --> A["College A · College Admin<br/>setup, generate, publish"]
    P --> B["College B · College Admin<br/>its own data, fully separate"]
    A --> C1["CSE · Department Coordinator<br/>own department, approvals, leave cover"]
    A --> C2["ECE · Department Coordinator"]
    A --> C3["ME · Department Coordinator"]
    C1 --> T["Teachers<br/>own lectures, one-day moves, attendance, leave"]
    C1 --> S["Students<br/>own section, free rooms, read-only assistant"]
```

Every role sees only its own part. A college you are not in answers 404, exactly like one that doesn't exist. The
assistant follows the same rules, because it acts with the user's own login.

## How to test it (2 minutes)

1. Open **https://timetabl-ai.vercel.app/demo**.
2. Pick a college: **Demo Institute** or **GNDEC (demo)**, then a role, and click **Open**. Nothing to type.
3. Press **Ctrl+K** anywhere to ask the assistant.

| Role | Login (password `demo1234`) |
|---|---|
| College Admin | `admin@demo.timetabl.ai` |
| Department Coordinator | `cse.coordinator@demo.timetabl.ai` (also `ece.`, `me.`, `as.`) |
| Teacher | `vikram.singh@demo.timetabl.ai` (busiest week) · any `firstname.lastname@demo.timetabl.ai` |
| Student | `cse3a.01@demo.timetabl.ai` (any section, roll 01-60) |
| Platform owner | `owner@demo.timetabl.ai` |
| GNDEC (demo) | Demo page → *GNDEC* tab: Admin, 5 Coordinators, teachers, a student per section, the JPAL student |

**Create a college from scratch:** sign up, then follow [`docs/demo-data/PIET/HOW_TO_LOAD.md`](docs/demo-data/PIET/HOW_TO_LOAD.md)
(2 departments in about 5 minutes: Setup → upload 2 Excel files → Generate → 0 clashes → Publish).

<img src="docs/screenshots/demo_page.png" alt="Demo page with one-click logins" width="640">

---

## Core features: the timetable

### 1. Set up without help
A short wizard (shifts, periods, mess window, holidays) and **one Excel sheet per department**. Errors show per row
before anything is saved; teachers are suggested fairly; a whole-year student list can be split into sections.

**Use it:** *Setup* → answer each step · *Departments* → *Download sheet* → fill → *Upload filled sheet* → *Mark Ready*.

| Setup wizard | Department data and Excel import |
|---|---|
| ![Setup wizard](docs/screenshots/setup.png) | ![Department page](docs/screenshots/department.png) |

### 2. One click: the whole college, clash-free
CP-SAT places every class: labs as blocks with parallel batches, combined classes, electives across departments,
1 or 2 shifts, shared and borrowed rooms, Must / Try rules, and a lunch gap for every section inside the mess window,
every day. An **independent validator** (no code shared with the solver) checks the result.

**Use it:** *Home* → **Generate** → check *Published · 0 clashes* → **Publish**.

![Timetable with the trust bar: Published, 0 clashes](docs/screenshots/timetable.png)

### 3. Section, teacher and room views
Colour-coded by subject, light and dark, on any phone. *Weekly plan* or *This week* with real dates.
Excel and PDF export for notice boards (*Download*).

![Teacher view](docs/screenshots/teacher_view.png)

### 4. Move a class: the app suggests where
Click or drag a class: **suggested slots** already have the teacher, every student and a room free (with the room
named). Green / amber / red on the grid; you review the result before it applies. Teachers send it as a request.

**Use it:** *Timetable* → *Weekly plan* → click a class → pick a suggested slot → *Apply*. None suits? *Ask the assistant*.

![Suggested slots while moving a class](docs/screenshots/move_suggestions.png)

### 5. One-day changes and makeup classes
Change one real date only; the weekly plan stays. The finder lists times when the teacher, all students and a room
are free. Students and teachers involved are told at once.

**Use it:** *Timetable* → *This week* → click a class → pick a free time, or cancel for the day.

![One-day change panel](docs/screenshots/one_day.png)

### 6. Every change logged and undoable
Who, what, when and how (manual, drag, assistant, system). *Undo* any change; approve teachers' move requests.

![Changes page with Undo](docs/screenshots/changes.png)

---

## Extra features: around the timetable

### 7. Talk to the assistant: it does the change beside you
Typed (**Chat**) or spoken (**Talk**, hands-free), in **English or Hinglish**. It answers aloud, opens the right
timetable next to the chat, and prepares the change as a card. **Nothing changes until you click Apply.**
Common questions (next class, free rooms, where is a teacher, undo) get **instant answers** without AI.

**Use it:** *Ctrl+K* → *Chat* or *Talk* → e.g. "Which rooms are free right now?", "Move CSE-3A DBMS to Friday".

![Assistant beside the timetable](docs/screenshots/assistant_instant.png)

### 8. Teacher away? A cover plan in seconds
Every affected class gets a ranked substitute (same subject, free then, fair load) or is cancelled, chosen per year.
Apply → validated one-day changes, notifications, undo.

**Use it:** say "Dr. Harpreet Kaur is away tomorrow, plan cover", or *Home* → *Teacher away*.

![Cover plan card](docs/screenshots/assistant_cover.png)

### 9. A home for every role

| Admin / Coordinator: today at a glance | Teacher: now, next, Take attendance |
|---|---|
| ![Admin Home](docs/screenshots/admin_home.png) | ![Teacher Home](docs/screenshots/teacher_home.png) |

| Student on a phone | Student assistant (read-only) |
|---|---|
| <img src="docs/screenshots/student_phone.png" alt="Student Home on a phone" width="260"> | ![Student assistant](docs/screenshots/student_assistant.png) |

### 10. Daily college life
Attendance on every class (students see "can miss N more"), office hours and doubt slots, meetings when chosen
teachers are all free, room booking for events (free rooms only, approved by the room's Coordinator), notices.
Nothing booked ever clashes with a class.

| Attendance | Room booking for events |
|---|---|
| ![Attendance](docs/screenshots/attendance_teacher.png) | ![Room booking](docs/screenshots/events.png) |

### 11. A ready SaaS
Many colleges on one platform, each kept apart. The platform owner sees every college's progress, health and
assistant cost, and sets plan, read-only or pause. Indicative plans: **Starter** free (one department) ·
**College** ₹25 per student per year · **University** custom.

![Platform owner view](docs/screenshots/platform.png)

---

## Testing datasets

| Dataset | What | Where |
|---|---|---|
| **Demo Institute of Technology** | Built in: 4 departments, 12 sections, 2 overlapping shifts, 40 teachers, 720 students, combined classes, a pooled open elective | Demo page |
| **GNDEC (demo)** | Re-engineered from GNDEC's public timetables, rooms and labs (every name made up): CSE, IT, Mechanical, Civil + Applied Sciences, 28 sections, 1,662 students, 96 teachers, 51 rooms, the JPAL lab for selected final-year CSE students | Demo page (*GNDEC* tab) · Excel files in [`docs/demo-data/GNDEC/`](docs/demo-data/GNDEC/) |
| **PIET (sample)** | The same data under another name, for creating a college from scratch (`@piet.test` logins) | [`docs/demo-data/PIET/`](docs/demo-data/PIET/) |
| **Blank template** | The department format with headings only and a *Read me* sheet | [`docs/demo-data/GNDEC/Timetabl_blank_template.xlsx`](docs/demo-data/GNDEC/Timetabl_blank_template.xlsx) |

## Results

| | |
|---|---|
| **0 clashes** | on every generated timetable and every change, checked by the independent validator |
| **238 classes** | Demo Institute, generated in under a minute |
| **570 classes** | GNDEC demo, 1,662 students |
| **237 of 238 stay** | after a mid-semester change with *Keep the current timetable* (about 4 s) |
| **~1 s** | instant answers; agentic requests about 8 s and about ₹2 |
| **187 tests** | 136 backend (engine, roles, college isolation, every workflow) + 51 assistant |

## How it is built

```
 Browser ──► Next.js web app (Vercel)
               │ REST                          │ streamed chat, voice
               ▼                               ▼
        FastAPI backend  ◄──── REST ────  FastAPI assistant (Claude tool use)
        CP-SAT · validator · Excel · notify     tools = backend calls with the user's login
               │                         (backend + assistant: one Fly.io machine)
               ▼
        Supabase Postgres
```

| Part | Tech |
|---|---|
| Web app | Next.js 15, TypeScript, Tailwind |
| Backend | Python 3.12, FastAPI, Pydantic, Google OR-Tools CP-SAT, openpyxl, ReportLab, SQLAlchemy |
| Assistant | FastAPI, Anthropic SDK: Claude Sonnet 5.5 (agentic), Haiku 5.5 (look-ups), Opus 5.5 (retry); OpenAI speech |
| Data | Supabase Postgres (SQLite locally); our own logins (scrypt + signed tokens) |

**Golden rules:** timetables come from the algorithm, never from the AI · every timetable and change passes the
validator · the assistant prepares, a person clicks Apply · every change is logged and can be undone.

## Run it locally

**Quickest:** double-click `start-local.bat`. It starts the backend, the assistant and the web app, then opens the
browser. Step by step (Python 3.12, Node 22):

```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
cd chatbot && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8001
```

```bash
cd frontend && npm install && npm run dev
```

Settings go in `backend/.env` and `chatbot/.env` (copy the `.env.example` files; `.env` files are never committed):
`DATABASE_URL` (Supabase; empty = a local SQLite file), `ANTHROPIC_API_KEY` (the assistant), `OPENAI_API_KEY`
(natural voice, optional). Without the keys, everything else still works. Open http://localhost:3000.

Tests:

```bash
cd backend && .venv/Scripts/python -m pytest
```

```bash
cd chatbot && .venv/Scripts/python -m pytest
```

On a laptop with little memory, set `SOLVER_WORKERS=2` before the backend tests.

## Deploy

Vercel (web app) + Fly.io (backend and assistant in one machine, billed per second) + Supabase (database).
Step by step: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Progress by stage

| Stage | What it delivers | Tag |
|---|---|---|
| 1. Engine | Generator, independent validator, quality score, plain-language feasibility checks | `stage-1-engine` |
| 2. See it | Backend API + web app: section / teacher / room views, Generate | `stage-2-see-it` |
| 3. Edit it | Drag and drop with repair, review before apply, undo, one-day changes | `stage-3-edit-it` |
| 4. Real SaaS | Colleges, logins, roles, invites, student logins, database | `stage-4-real-saas` |
| 5. Set it up | Setup wizard, Excel import, suggestions, Ready flow, electives, rules, block times | `stage-5-set-it-up` |
| 6. Chatbot | Role-aware assistant with change cards and insights | `stage-6-chatbot` |
| 7. Ship | Publish, exports, notifications, requests, attendance, Today view, makeup finder | |
| 8. Grow | Language and voice, teacher booking, auto-sectioning, platform owner view, minimal-change regenerate | `stage-8-grow` |
| 9. Submission | Teacher leave and cover plans; faster assistant (router, instant answers, Talk mode, screen-driving); suggested slots; events, notices; home page; GNDEC and PIET datasets; deployment | |
