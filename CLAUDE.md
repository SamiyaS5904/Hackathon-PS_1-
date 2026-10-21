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
5. **Tenant isolation:** every tenant table has `org_id`; Supabase RLS enforces it; the backend reads `org_id` + role from the JWT, **never from the request body**.
6. **Every change is logged** (who, what, when, how: manual / drag / chatbot / system, reason) and can be undone.
7. **Configurable, not hard-coded.** Anything that differs between colleges (shifts, periods, breaks, lab length, rules, structure levels) is data, not code.
8. **Small working commits** after every step (see §10). Never leave `main` broken.
9. **Ask the user before big decisions** (architecture, new dependencies, scope changes). Explain options in plain language; the user prefers numbered plain-text questions.
10. Terminology: the department-level role is **Department Coordinator** (never "HOD").

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
| View | everything | own dept + shared | own + dept | own section / electives |
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
| Time grid | Working days, shift timings, lecture duration, **one lab duration for the whole college**, fixed breaks, and a **flexible lunch**: admin gives the mess window per shift, the solver picks each year's lunch period inside it (same every day) for the best timetable and venue use |
| Venue | Room with type (lecture hall / lab / seminar / auditorium), capacity, tags, owner dept or *Shared* |
| Section | A group of students that always sits together (atomic). Room capacity ≥ strength |
| Lab batch | Sub-group of a section for labs (A1/A2), runs in parallel |
| Subject | Code, dept, year, lecture/tutorial/lab hours per week |
| Allotment | Subject + section(s)/batch + teacher. Several sections = combined class |
| Elective group | Parallel options in the same slot (ML / Cloud / IoT), students split by choice |
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
- **Hard:** no teacher / venue / section / batch double-booking; venue type + capacity; shift windows (strict); breaks & holidays; teacher block times; labs as consecutive blocks of the college lab length, batches in parallel; combined classes & elective groups together; all *Must* rules.
- **Soft (quality score):** balanced teacher load (max per day, max consecutive), minimal student gaps, same subject ≤1/day, venue size fit / utilisation, all *Try* rules with weights.
- Infeasible input → explain which rule group conflicts in plain language (never a silent failure).

---

## 8. Version scope

> Confirmed by the user on the V1/V2 board (2026-10-21).

**V1: must ship (hackathon)**
- Self-signup workspace + demo college; roles + email invites (Admin, Coordinator, Teacher)
- **Student light login with simple dummy emails** (e.g. `cse3a.01@demo.timetabl.ai`, seeded for the demo college; email + password via Supabase Auth)
- Setup wizard (shifts incl. 2-shift strict, lecture/lab length, breaks per year, holidays list, semester dates)
- Venues, departments, sections, subjects, teachers; Excel import with row-level error preview
- Coordinator Ready flow + admin readiness checklist dashboard
- CP-SAT college-wide generation + validator + quality score; labs as blocks with parallel batches; **parallel elective groups**
- **Rules page** (college + dept rule cards)
- Section / teacher / room views, colour-coded; publish; Excel + PDF export
- Drag & drop with live clash check; one-day overrides; teacher one-day instant / permanent needs approval; **teacher block times** (auto-confirm if clash-free)
- Audit log with undo; in-app notifications
- Chatbot side panel: role-scoped Q&A (student read-only) + edits via solver repair + diff preview + **proactive insights after generation**

**V1: if time** (in this order)
Teacher allotment suggestion · substitutes on leave · makeup / extra class finder · email notifications · Now & Next TV board

**V2: roadmap**
Super admin panel · Google login for students · Hinglish chatbot · auto-sectioning from year list · mid-semester regenerate with minimal change · NAAC/NBA workload report · Google Calendar sync · QR posters · teacher booking (doubt slots, meetings) · WhatsApp/SMS · plain-language rules via chatbot · book/makeup/notify via chat · timetable version compare · **attendance** (per-college rule, e.g. 75%, shown beside the student timetable)

---

## 9. Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript strict, Tailwind, shadcn/ui, TanStack Query, dnd-kit → Vercel |
| Backend | Python 3.12, FastAPI, Pydantic v2, OR-Tools CP-SAT, openpyxl, a PDF library → Render/Railway |
| Chatbot | Python 3.12, FastAPI, Anthropic SDK (Claude tool use), SSE streaming → Render/Railway |
| Data / Auth | Supabase: Postgres, Auth (magic link, Google), Row Level Security |
| Email | Resend |
| LLM models | `claude-sonnet-5-5` (agent), `claude-haiku-5-5` (light Q&A / routing) |

**Environment variables** (never commit values; keep `.env.example` files current)
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (backend only), `SUPABASE_JWT_SECRET`, `ANTHROPIC_API_KEY` (chatbot only), `RESEND_API_KEY`, `BACKEND_URL`, `CHATBOT_URL`, `NEXT_PUBLIC_*` for public frontend values.

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
| 8. If time | V1-if-time list in order | |

---

## 11. Commands

_To be filled in when each part is scaffolded._

| Task | Command |
|---|---|
| Frontend dev | `cd frontend && npm run dev` |
| Backend dev | `cd backend && uvicorn app.main:app --reload` |
| Chatbot dev | `cd chatbot && uvicorn app.main:app --reload --port 8001` |
| Backend tests | `cd backend && pytest` |
