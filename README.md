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
| 5. Set it up | Setup wizard, Excel import, Coordinator "Ready" flow, teacher allotment suggestions, rules, elective slots and pooled cross-department groups, teacher block times | ⏳ Next | |
| 6. Chatbot | Role-aware assistant (typing or voice): answers questions such as "when am I free next week?", proposes edits, flags problems | ⏳ | |
| 7. Ship | Publish, Excel / PDF export, notifications, deploy | ⏳ | |

### Results on the demo college
12 sections · 37 teachers · 15 rooms · 2 overlapping shifts · combined classes · lab batches

- **232 classes placed, 0 clashes** (checked by a validator that shares no code with the solver)
- **Quality 84/100** in 30 s: no idle gaps for students, no single-class days, balanced teacher load, right-sized rooms
- Move options in ~0.02 s; repair moves in 0.7–2 s
- 40 automated backend tests (engine, editing, one-day changes, login, roles, college isolation)

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

## Tech

Next.js 15 · Tailwind · FastAPI · Google OR-Tools CP-SAT · (Stage 4+) Supabase · Claude API for the assistant only. Timetables are always built by the algorithm, never by the AI.
