# Timetabl.ai: run it and find every feature

## 1. Start it (one double-click)

1. Open the folder `D:\Hackathon` and double-click **`start-local.bat`**.
2. Three black windows open (backend, assistant, web app). The first start builds the web app: wait 1–2 minutes.
3. The browser opens **http://localhost:3000** by itself.
4. To stop: close the three "Timetabl" windows.

Data lives in Supabase (your `backend/.env`), so everything you do stays saved.
If a window shows an error, send me a screenshot of it.

## 2. Log in

The login page has **one-click demo buttons** (password for all: `demo1234`):

| Button | Who | Email |
|---|---|---|
| College Admin | runs the whole college | `admin@demo.timetabl.ai` |
| CSE Coordinator | Computer Science department only | `cse.coordinator@demo.timetabl.ai` |
| Teacher | Dr. Anita Sharma | `anita.sharma@demo.timetabl.ai` |
| Student | CSE-3A, roll 01, lab batch B1 | `cse3a.01@demo.timetabl.ai` |

Any student works: `cse3a.05@…`, `ece2a.12@…` (section + roll 01–60). To log in as someone else,
use the **log out** icon (bottom-left, or top-right on a phone).

Everywhere: **sun/moon icon** = light/dark theme · **bell** = notifications · **Ask** button or
**Ctrl+K** = AI assistant (also by voice: the mic button, in Chrome/Edge).

## 3. Where each feature is

### College Admin

| Feature | Where |
|---|---|
| What to do next + timetable health (clashes, quality) | **Dashboard**, top card and the 4 numbers |
| Departments ready checklist | **Dashboard** → "Departments ready" |
| Why the quality score is what it is | **Dashboard** → "Why the quality score is …" |
| Suggestions ("Prof X has 4 periods on Tue") + ask the assistant | **Dashboard** → "Worth a look" |
| **Generate** the whole college | **Timetable** → *Regenerate* (top right), or Dashboard when there is none (~45 s) |
| **Publish** for teachers and students | **Timetable** / Dashboard → *Publish* (appears while a draft waits) |
| View by section / teacher / room | **Timetable** → *Section · Teacher · Room* + the dropdown |
| **Drag a class** to a new time (green = free, amber = others move, red = not allowed) → review → Apply | **Timetable** → *Weekly plan* → drag, or click a class then click a slot |
| **One-day change** (cancel or move just for one date) | **Timetable** → *This week* → click a class |
| Undo the last change, see who changed what | **Activity** (sidebar) |
| Excel / PDF for notice boards (one or all sections / teachers / rooms) | **Timetable** → *Download* |
| Setup wizard: days, lab length, 1 or 2 shifts, periods, breaks, lunch window, holidays, semester dates, departments, rooms | **College setup** |
| Department data, Excel import, teacher suggestions, Ready status | **Departments** → pick one |
| College / department rules (Must / Try) | **Rules** |
| Invite Coordinators and teachers | **People & invites** |
| Approve teachers' requests to move a class | **Change requests** |
| Read everything the college has entered | **College data** |

### Department Coordinator (CSE)

| Feature | Where |
|---|---|
| Department workspace: sections, subjects, teachers, who teaches what | **My department** |
| Excel: download the sheet (already filled), fill it, upload it → row-level errors | **My department** → *Download sheet* / *Upload filled sheet* |
| Teacher allotment suggestions with reasons → approve | **My department** → *Suggest for empty* / *Re-suggest all* |
| Mark the department Ready for the Admin | **My department** → *Mark department Ready* |
| Move or change own department's classes | **Timetable** (same as Admin, own department only) |
| Teachers' change requests → *Review and approve* / *Decline* | **Change requests** (dashboard shows a banner when some wait) |
| Department rules | **Rules** |

### Teacher (sees only their own lectures)

| Feature | Where |
|---|---|
| My timetable on real dates | **My timetable** → *This week* |
| Cancel or move my lecture for one day (instant, students notified) | **My timetable** → *This week* → click a lecture |
| Ask the Coordinator to move a lecture permanently | **My timetable** → *Weekly plan* → click a lecture → click a slot → reason → *Send request* |
| Follow my requests (waiting / approved / declined) | **My requests** |
| Times I can't teach (confirmed instantly if no clash) | **My availability** |
| Download my timetable | **My timetable** → *Download* |

### Student (sees only their own classes)

| Feature | Where |
|---|---|
| My week, including cancellations and moves | **My timetable** → *This week* / *Weekly plan* |
| Download / print my timetable | **My timetable** → *Download* / *Print* |
| "When am I free next week?", "Where is Dr. Kaur now?", "Which room is free?" | **Ask** (Ctrl+K) |
| Changes to my classes | the **bell** |

## 4. A 5-minute demo script

1. **Admin** → Dashboard: 0 clashes, quality score, every department Ready.
2. **Timetable** → section CSE-1A → *Teacher* view → *Room* view (same timetable, three angles).
3. Drag a class → green / amber / red slots → drop on amber → the review shows exactly which classes move,
   "Checked: no clashes" → **Apply** → Activity → **Undo**.
4. *This week* → click a class → cancel it for Friday with a reason → log in as a **Student** of that
   section → the bell shows the cancellation, the grid shows it struck through.
5. **Teacher** → *Weekly plan* → ask to move a lecture → **Coordinator** → Change requests → Review →
   Apply → the teacher gets "approved".
6. **Ask** (Ctrl+K): as Admin "Move CSE-2B's Monday DBMS lecture to Friday morning" → a card with the
   checked change → Apply. As a Student "I need to fix a meeting next week, when am I free?".
7. **Download** → PDF of all sections (notice board ready).
8. **Sign up** a new college → *Load sample college* or the setup wizard → Generate: works for any college.

Key message: the timetable is built by an algorithm (Google OR-Tools CP-SAT) and every timetable and every
change is checked by an independent validator, so no clash ever reaches anyone. The AI assistant only
answers and proposes; a person always clicks Apply.
