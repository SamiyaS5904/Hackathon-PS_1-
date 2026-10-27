# Timetabl.ai

**Clash-free college timetables, made in minutes and kept right all semester.** A multi-college web app: departments
fill in their data, the College Admin clicks Generate, and every section, teacher and room gets a timetable with no
clashes and fewer gaps. When a teacher is away or a class moves, an AI assistant plans the fix and a person applies
it with one click.

**Hackathon · Samiya Sehgal (URN 2302662)**

- **Live:** _web app link (Vercel) and API link go here after deployment_. Steps:
  [`docs/DEPLOY.md`](docs/DEPLOY.md).
- **Demo guide** (logins, where every feature is, a demo script): [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md).
- **Design and rules:** [`CLAUDE.md`](CLAUDE.md) · [`backend/CLAUDE.md`](backend/CLAUDE.md) ·
  [`frontend/CLAUDE.md`](frontend/CLAUDE.md) · [`chatbot/CLAUDE.md`](chatbot/CLAUDE.md).

## The problem

Hand-made college timetables clash: one room for two classes, one teacher in two places. Students have scattered
gaps and don't know where to sit in a free period. When a teacher is away, classes just vanish. Every change means
checking ten timetables by hand.

## What it does

| | |
|---|---|
| **Generate** | One click builds the whole college's timetable: 1 or 2 shifts, labs as blocks with parallel batches, combined classes, electives and pooled cross-department groups, shared and borrowed rooms, a lunch gap for every section inside the mess timings (chosen per day), rules (Must / Try), teacher block times. |
| **No clash, ever** | A separate validator (no shared code with the generator) checks every timetable and every change before anyone sees it. |
| **Set up without help** | Setup wizard, one Excel sheet per department with row-level errors, fair teacher suggestions, a readiness checklist, auto-sectioning from a whole-year list. |
| **See it** | Section, teacher and room views; Today and This week with real dates; light and dark; phones. |
| **Change it safely** | Drag and drop with green / amber / red slots (only classes that must move do); one-day cancel or move; makeup finder; teacher requests approved by the Coordinator; undo for every change; mid-semester regenerate that keeps the timetable. |
| **Teacher leave** | Teacher asks, Coordinator approves. A cover plan gives every class a ranked substitute (same subject first, fair load) or cancels it, chosen per year. Apply notifies the students, the teachers and the substitutes. |
| **Daily life** | Attendance, doubt slots and meetings, room booking for events (approved by the room's Coordinator), notices, notifications to only the people affected, Excel / PDF exports, tomorrow's brief. |
| **AI assistant** | Typed or spoken (Chat and hands-free Talk mode). It finds the facts, opens what it talks about on screen, and prepares changes as cards; **a person clicks Apply**. It acts with the user's own permissions. Common questions get instant answers without AI. |
| **SaaS** | Many colleges, each kept separate; roles from Super Admin (platform) to College Admin, Department Coordinator, teacher and student; plans, read-only and pause. |

## The AI assistant, in short

- **The timetable is always made by the algorithm (Google OR-Tools), never by the AI.** The assistant uses tools
  that call the same backend with the user's own login, so it can never do more than that person could by hand.
- **Changes are cards, never silent edits:** moves (checked for clashes), one-day changes, leave cover plans,
  bookings and undo all wait for the person's click.
- **Fast and cheap by design:**
  - *Instant answers:* "my next class", "free rooms now", "where is Dr. Arora", "show CSE-3A", "undo". They come
    straight from the timetable in about 0.6-1.5 s, at no AI cost.
  - *A model router:* Claude Sonnet 5.5 for agentic work (moves, leave, makeups, meetings), Claude Haiku 5.5 for
    simple look-ups, and Claude Opus 5.5 as a one-time retry if a call fails.
  - Measured on the demo college: agentic requests take about 7.7 s and ₹2; look-ups about ₹0.10. The College Admin
    sees the cost on a small card.
- **Voice:** OpenAI speech-to-text and natural text-to-speech (browser voice as fallback). It answers aloud
  sentence by sentence, you can interrupt it, and replies are in English by default with Hinglish as an option.

## Two demo colleges

| | Demo Institute of Technology | GNDEC (demo) |
|---|---|---|
| What | Built-in sample | Re-engineered from GNDEC's public timetables, rooms and labs (every name made up) |
| Size | 4 departments, 12 sections, 2 shifts, 44 teachers, 15 rooms | CSE, IT, Mechanical, Civil + Applied Sciences, years 1-4: 28 sections, 1,662 students, 96 teachers, 51 rooms and labs |
| Timetable | 238 classes, 0 clashes, quality 83-86 | 570 classes, 0 clashes, quality 79 (9 periods 08:30-17:30, a lunch gap for every section, the mess split across two lunch hours) |
| Special | combined classes, pooled open elective | the **JPAL lab** for about 30 selected final-year CSE students (the rest have a project review then), a final-year elective with 3 groups |

The GNDEC data is also available as one Excel file per department plus a blank template:
[`docs/demo-data/GNDEC/`](docs/demo-data/GNDEC/). That folder also has assistant test questions per role.

## Results on the demo college

12 sections · 44 teachers · 15 rooms · 2 overlapping shifts · combined classes · lab batches · a pooled open elective.

- **238 classes, 0 clashes**, quality 83-86/100, generated in 30-45 s.
- Teacher suggestions for a department in under 0.1 s. Move options in about 0.02 s, repairs in 0.7-2 s.
- Mid-semester change: *Keep the current timetable* moves **1 of 238** classes in about 4 s.
- Leave cover: substitutes for every class of a teacher's day in under a second, each checked by the validator.
- **Tests:** 130+ backend tests and 50 assistant tests.
  - Backend: engine, electives, rules, Excel, setup, editing, one-day changes, leave cover, regenerate, login and
    roles, college isolation, attendance, bookings, events, notices, platform, cost card.
  - Assistant: role-scoped tools, model router, agent loop, instant answers, voice, language.

## Run it locally

**Quickest:** double-click `start-local.bat`. It starts the backend, the assistant and the web app, then opens the
browser.

Step by step (Python 3.12, Node 22):

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

Settings go in `backend/.env` and `chatbot/.env`; copy them from the `.env.example` files, which are never
committed:
- `DATABASE_URL`: Supabase. Leave it empty to use a local SQLite file.
- `ANTHROPIC_API_KEY`: the assistant.
- `OPENAI_API_KEY`: natural voice. Optional.

Without the keys, everything else still works.

Open http://localhost:3000, then **Try the demo**. Every demo account's password is `demo1234`:

| Role | Login |
|---|---|
| College Admin | `admin@demo.timetabl.ai` |
| Department Coordinator | `cse.coordinator@demo.timetabl.ai` (also `ece.`, `me.`, `as.`) |
| Teacher | `anita.sharma@demo.timetabl.ai` (any teacher: `firstname.lastname@demo.timetabl.ai`) |
| Student | `cse3a.01@demo.timetabl.ai` (any section, roll 01-60) |
| Platform owner | `owner@demo.timetabl.ai` |
| GNDEC (demo) | `admin@gndec.demo`, `cse.coordinator@gndec.demo`; teachers and students are listed on the Demo page (*GNDEC* tab) |

Tests:

```bash
cd backend && .venv/Scripts/python -m pytest
cd chatbot && .venv/Scripts/python -m pytest
```

On a laptop with little memory, set `SOLVER_WORKERS=2` before the backend tests.

## Deploy

Vercel (web app) + Render free (backend and assistant, no card) or Fly.io (one always-on machine, billed per
second) + Supabase (database). Step by step: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## How it is built

```
 Browser ──► Next.js web app (Vercel)
               │ REST                          │ streamed chat, voice
               ▼                               ▼
        FastAPI backend  ◄──── REST ────  FastAPI assistant (Claude tool use)
        engine · validator · Excel · notify     tools = backend calls with the user's login
               │
               ▼
        Supabase Postgres
```

| Part | Tech |
|---|---|
| Web app | Next.js 15, TypeScript, Tailwind |
| Backend | Python 3.12, FastAPI, Pydantic, Google OR-Tools CP-SAT, openpyxl, ReportLab, SQLAlchemy |
| Assistant | FastAPI, Anthropic SDK (Claude Sonnet / Haiku / Opus 5.5), OpenAI audio (optional) |
| Data | Supabase Postgres (SQLite locally); our own logins (scrypt + signed tokens) |

## Progress by stage

Each finished stage has a Git tag.

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
| 9. Submission | Teacher leave and cover plans; faster, cheaper assistant (router, instant answers, Talk mode, screen-driving); events, notices, mess split; home page; deployment | |
