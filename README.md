# Timetabl.ai

Clash-free college timetables for any college: a multi-college (SaaS) web app with a timetable engine, safe editing and (coming) an AI assistant.

**Hackathon 1 · Samiya Sehgal (URN 2302662)**

Project rules and full design: [`CLAUDE.md`](CLAUDE.md) · [`backend/CLAUDE.md`](backend/CLAUDE.md) · [`frontend/CLAUDE.md`](frontend/CLAUDE.md) · [`chatbot/CLAUDE.md`](chatbot/CLAUDE.md) · Session 1 summary: [`docs/`](docs)

## Progress by stage

Each finished stage has a Git tag, so its exact state can be opened on GitHub.

| Stage | What it delivers | Status | Tag |
|---|---|---|---|
| Planning | Roles, rules, algorithm choice, V1/V2 scope, architecture, project guides | ✅ Done | — |
| **1. Engine** | CP-SAT timetable generator, independent clash validator, quality score, feasibility checks with plain-language errors, room-capacity edge cases, demo college | ✅ Done | `stage-1-engine` |
| **2. See it** | FastAPI backend + Next.js app: dashboard, section / teacher / room views, Generate with live progress | ✅ Done | `stage-2-see-it` |
| **3. Edit it** | Drag and drop with green / amber / red slots, solver repair that moves only what's needed, review before apply, undo, activity log, one-day cancel / reschedule on real dates | ✅ Done | `stage-3-edit-it` |
| **4. Real SaaS** | Signup creates a college workspace, login, roles (Admin / Department Coordinator / Teacher / Student), invite links, students log in with college emails and see only their own timetable, every college's data kept separate, saved in a database (SQLite locally, Supabase Postgres in production) | ✅ Done | `stage-4-real-saas` |
| **5. Set it up** | Setup wizard (days, 1 or 2 shifts, periods and breaks, mess window, lab length, semester dates, holidays, departments, shared rooms, sections → shifts); department workspace with pre-filled Excel download and upload with row-level errors; teacher allotment suggestions with reasons; Ready flow and readiness checklist; elective slots and pooled cross-department groups; rule cards (Must / Try); teacher block times; "data changed, regenerate" safety | ✅ Done | `stage-5-set-it-up` |
| **6. Chatbot** | Assistant side panel on every page (Ctrl+K, typing or browser voice): students ask "when am I free next week?", "where is Dr. Kaur now?", "why is my lab on Friday?"; staff get move proposals and one-day changes as cards they Apply or Discard (the assistant never writes on its own, and uses the logged-in user's own permissions); "Worth a look" insights after generation | ✅ Done | `stage-6-chatbot` |
| 7. Ship | Publish (teachers and students see only published timetables), Excel / PDF for notice boards, in-app notifications for the people affected, teacher change requests approved by the Department Coordinator, light / dark theme, phone layout, fast on a remote database (memory first, background saves); deploy guide in [`docs/DEPLOY.md`](docs/DEPLOY.md) | 🟡 Built, deploying | |

### Results on the demo college
12 sections · 40 teachers · 15 rooms · 2 overlapping shifts · combined classes · lab batches · a 3rd-year open elective pooled from 4 sections and 3 departments

- **238 classes placed, 0 clashes** (checked by a validator that shares no code with the solver)
- **Quality 83-86/100** in 30-45 s: no idle gaps for students, no single-class days, balanced teacher load, right-sized rooms
- Elective groups meet together, each in a room for its members (Robotics in an ME room); every student sees only their own group
- Teacher suggestions for a whole department in under 0.1 s
- Move options in ~0.02 s; repair moves in 0.7–2 s
- 63 automated backend tests (engine, electives, rules, suggestions, Excel, setup, editing, one-day changes, login, roles, college isolation, assistant facts) + 12 assistant tests (role-scoped tools, agent loop)

## Run it locally

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Frontend (Node 22):

```bash
cd frontend
npm install
npm run dev
```

Assistant (optional, Python 3.12):

```bash
cd chatbot
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8001
```

The assistant needs a Claude API key: copy `chatbot/.env.example` to `chatbot/.env` and set `ANTHROPIC_API_KEY` (the file is git-ignored). Without it, the rest of the app works and the panel says the assistant isn't set up.

Open http://localhost:3000 and use a one-click demo login (password `demo1234`):

| Role | Email |
|---|---|
| College Admin | `admin@demo.timetabl.ai` |
| Department Coordinator | `cse.coordinator@demo.timetabl.ai` (also `ece.`, `me.`, `as.`) |
| Teacher | `anita.sharma@demo.timetabl.ai` (any teacher: `firstname.lastname@demo.timetabl.ai`) |
| Student | `cse3a.01@demo.timetabl.ai` (any section and roll number 01-60) |

As Admin, click **Generate timetable**. To use Supabase, copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL`.

Tests and the command-line demo:

```bash
cd backend
.venv/Scripts/python -m pytest
.venv/Scripts/python -m app.cli --section cse-3a
```

## Deploy

Vercel (web app) + Railway (backend, assistant) + Supabase (database): step by step in [`docs/DEPLOY.md`](docs/DEPLOY.md). Each service folder has a `railway.toml`; `render.yaml` is an alternative.

## Tech

Next.js 15 · Tailwind · FastAPI · Google OR-Tools CP-SAT · (Stage 4+) Supabase · Claude API for the assistant only. Timetables are always built by the algorithm, never by the AI.
