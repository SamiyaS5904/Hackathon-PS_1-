# frontend/CLAUDE.md: Web app

> Read the root [`CLAUDE.md`](../CLAUDE.md) first (product, roles, golden rules, V1 scope). This file covers only the web app.

## Purpose
One Next.js app that serves **every role** (College Admin, Department Coordinator, Teacher, Student) plus public pages (landing, share links, TV board). It talks to:
- **backend** (REST, Supabase JWT in `Authorization`) for all data, generation, edits, exports
- **chatbot** (SSE stream, same JWT) for the chat side panel
- **Supabase Auth** directly for sign-up / login / magic links

The frontend **never decides permissions or clashes on its own**. It may *pre-check* for nice UX (e.g. drag highlights), but the backend's answer is final.

## Stack
Next.js 15 (App Router) · TypeScript strict · Tailwind CSS · shadcn/ui · lucide-react icons · TanStack Query (server state) · Zustand (small UI state only) · dnd-kit (drag & drop) · react-hook-form + zod (forms) · @supabase/ssr (auth) · sonner (toasts). Deploy on Vercel.

## Folder structure (planned)
```
frontend/
├── app/
│   ├── (marketing)/            landing page, pricing placeholder
│   ├── (auth)/                 login, signup, accept-invite, student login
│   ├── (app)/[orgSlug]/        everything behind login, scoped to one college
│   │   ├── dashboard/          role-aware home
│   │   ├── setup/              setup wizard (Admin)
│   │   ├── departments/[deptId]/  Coordinator workspace (sections, subjects, teachers, allotment, Ready)
│   │   ├── venues/  rules/  import/
│   │   ├── timetable/          grid views: section / teacher / venue, generate, publish
│   │   ├── changes/            pending approvals, one-day changes, block times
│   │   ├── audit/              audit log + undo
│   │   ├── notifications/
│   │   └── me/                 Teacher / Student personal timetable
│   ├── share/[token]/          public read-only section timetable
│   └── tv/[token]/             Now & Next board (if time)
├── components/
│   ├── ui/                     shadcn primitives (do not edit by hand beyond theming)
│   ├── timetable/              TimetableGrid, SessionCard, SlotCell, DiffView, Legend
│   ├── chat/                   ChatPanel, MessageList, ProposalCard, InsightCard
│   ├── wizard/                 WizardShell, step components
│   └── layout/                 AppShell, Sidebar, TopBar, RoleGate
├── lib/
│   ├── api/                    typed backend client (generated from backend OpenAPI)
│   ├── chat/                   SSE client for chatbot
│   ├── supabase/               browser + server clients
│   └── utils/
└── types/                      generated API types; never hand-edit generated files
```

## Screens by role (V1)

| Screen | Admin | Coordinator | Teacher | Student |
|---|---|---|---|---|
| Dashboard | readiness checklist per dept, quality score, pending approvals, insights | dept progress, pending teacher requests | today's classes, my requests | today + next class, changes today |
| Setup wizard | ✅ | | | |
| Venues / Rules | ✅ (college + shared) | own dept venues + dept rules | | |
| Department workspace | ✅ any dept | ✅ own dept | | |
| Excel import | ✅ | ✅ own dept | | |
| Timetable grid (generate / publish / edit) | ✅ | edit own dept | own lectures | view only |
| Changes & approvals | ✅ | ✅ | request / one-day change / block time | |
| Audit log | ✅ | own dept | | |
| Chat panel | full | dept | own lectures | read-only Q&A |

Hide what a role can't use (don't show disabled buttons for things they will never be allowed to do). Use `RoleGate` + server-side checks.

## Setup wizard (key UX)
One topic per screen, progress bar, **save & resume**, sensible defaults pre-filled, live validation.
Steps: College basics → **Shifts** (1 or 2; if 2: timings for each + how students are divided: by year / dept / section, day scholar vs hosteller → section table with Morning/Evening toggle) → Working days & lecture duration → Lab duration (one for the whole college) → Breaks (count, time, length, per year) → Holidays upload + tentative semester dates → Structure levels (Program / Year / Section / Batch toggles) → Departments → Venues → Invite Coordinators → Done (checklist).
Show **live feasibility hints** from the backend (e.g. "CSE needs 34 lab periods but only 30 lab slots exist").

## TimetableGrid (the most important component)
- Rows = periods (with break rows visually distinct), columns = working days. One component for **section, teacher and venue** views (pivot by prop).
- `SessionCard`: subject short name (bold), teacher, venue, batch/elective tag; colour by subject (stable hash → palette, accessible contrast in light & dark).
- Overrides on the date view: cancelled = struck-through + muted; moved/extra = badge "Changed today".
- **Drag & drop:** on drag start, ask backend for valid target slots (`/check-move`), colour cells **green** (valid), **red** (clash, with tooltip reason), **amber** (valid but lowers quality). On drop → backend repair → `DiffView` → Apply.
- Print-friendly CSS; export buttons call backend (Excel/PDF).
- Readable at a glance: no more than 3 lines per card, abbreviations with full name on hover.

## Chat panel
- Right-side drawer on every `(app)` page, toggled by a button and **Ctrl/Cmd + K**.
- Sends `{message, page_context}`, where `page_context` = what the user is looking at (view type, section/teacher/venue id, selected date, selected session) so "move this class" works.
- Streams tokens via SSE; renders tool progress ("Checking free rooms…").
- A `ChangeProposal` renders as a **ProposalCard** with a mini `DiffView` + **Apply / Discard / Try another way**. Apply calls the backend, not the chatbot.
- **InsightCard** for proactive insights after generation (e.g. "Dr. Kaur has 6 lectures on Monday. Rebalance?").
- Suggested prompts per role on empty state (English in V1; Hinglish is V2).

## Core vs secondary placement (see root CLAUDE.md §2A)
- **Sidebar order:** Dashboard → Timetable → Setup / Data (venues, departments, sections, teachers, subjects) → Changes. Secondary items (Rules, Audit, Reports, Settings) sit below a divider.
- **Primary button** (filled, accent) only for the core action of the screen: *Generate*, *Publish*, *Apply*, *Continue* in the wizard. Everything else is outline/ghost.
- **Timetable grid** takes the main area. Chat opens as a right drawer beside it; notifications live behind the bell; exports in a "Download" menu.
- **Dashboard top:** a "Next step" card (e.g. "2 departments not Ready", "Generate timetable") and timetable health (clashes = 0, quality score). Insights and activity go below.

## Design system
- Clean SaaS look (Linear / Notion): neutral greys, one accent colour, generous whitespace, 8px radius, subtle borders, no heavy shadows/gradients.
- Light + dark mode via CSS variables (shadcn theming). Every colour must work in both.
- Typography: Inter (or Geist); clear hierarchy; sentence case.
- Plain language in UI copy: "section", "period", "venue", "Department Coordinator". No solver jargon ("CP-SAT", "constraint") in user-facing text; say "rules".
- Every list/page has **empty state** (what it is + primary action), **loading skeleton**, **error state with retry**.
- Accessible: keyboard navigable grid and dialogs, focus rings, aria labels on icon buttons, colour never the only signal (add icons/text for clash/valid).
- Responsive: dashboards and personal timetable usable on phone (students/teachers mostly on mobile); full grid editing optimised for desktop.

## Conventions
- Server Components by default; `"use client"` only where interaction needs it.
- Data fetching via TanStack Query hooks in `lib/api/hooks/*`; one hook per resource; invalidate on mutations.
- API types come from backend OpenAPI (`npm run gen:api`). Never duplicate a type by hand.
- Forms: react-hook-form + zod; show field-level errors.
- No secrets in the frontend; only `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_CHATBOT_URL`.
- Components: PascalCase files; hooks `useXxx`; keep components < ~200 lines, split otherwise.

## Definition of done (frontend)
Works for the right role and is hidden for others · empty / loading / error states · light + dark checked · keyboard usable · no console errors · `npm run lint` and `npm run typecheck` clean · committed.

## Commands
_Fill in after scaffolding:_ `npm run dev` · `npm run build` · `npm run lint` · `npm run typecheck` · `npm run gen:api`
