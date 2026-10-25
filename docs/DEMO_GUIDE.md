# Timetabl.ai: run it and find every feature

## 1. Start it (one double-click)

1. Open the folder `D:\Hackathon` and double-click **`start-local.bat`**.
2. Three black windows open (backend, assistant, web app). The first start builds the web app: wait 1–2 minutes.
3. The browser opens **http://localhost:3000** by itself.
4. To stop: close the three "Timetabl" windows.

Data lives in Supabase (your `backend/.env`), so everything you do stays saved.
If a window shows an error, send me a screenshot of it.

## 2. Log in

On the login page click **Try the demo college** (small link under the form). The demo page has one-click
entries for every role (password for all: `demo1234`):

| Choice | Who | Email |
|---|---|---|
| Platform owner (SaaS) | the Timetabl.ai team: every college, plans, health, pause / read-only | `owner@demo.timetabl.ai` |
| College Admin | runs the whole college | `admin@demo.timetabl.ai` |
| Department Coordinator | pick a department (CSE, ECE, ME, AS) | `cse.coordinator@demo.timetabl.ai` |
| Teacher | Dr. Anita Sharma | `anita.sharma@demo.timetabl.ai` |
| Student | pick any section, roll 01 | `cse3a.01@demo.timetabl.ai` |

Any student works by hand: `cse3a.05@…`, `ece2a.12@…` (section + roll 01–60). To switch user, use the
**log out** icon (bottom-left, or top-right on a phone).

Everywhere: **sun/moon icon** = light/dark theme · **bell** = notifications · **Ask** button or
**Ctrl+K** = AI assistant (also by voice: the mic button, in Chrome/Edge; answers to spoken questions are read aloud).
The assistant answers in your language: English → English, Hinglish (Roman) → Hinglish, e.g. "kal mera pehla lecture kab hai?"

## 3. Where each feature is

### College Admin

| Feature | Where |
|---|---|
| What to do next + timetable health (clashes, quality) | **Dashboard**, top card and the 4 numbers |
| Departments ready checklist | **Dashboard** → "Departments ready" |
| Suggestions ("Prof X has 4 periods on Tue") | **Ask** panel (Ctrl+K), top of the chat |
| **Generate** the whole college | **Timetable** → *Regenerate* (top right), or Dashboard when there is none (~45 s) |
| Mid-semester change (new teacher, block time): regenerate moving as few classes as possible | **Timetable** → *Regenerate* → *Keep the current timetable* (summary: "237 stayed, 1 moved") |
| **Publish** for teachers and students | **Timetable** / Dashboard → *Publish* (appears while a draft waits) |
| View by section / teacher / room | **Timetable** → *Section · Teacher · Room* + the dropdown |
| **Drag a class** to a new time (green = free, amber = others move, red = not allowed) → review → Apply | **Timetable** → *Weekly plan* → drag, or click a class then click a slot |
| **One-day change** (cancel or move just for one date) | **Timetable** → *This week* → click a class |
| **Makeup class finder** (free times in the next 7 days for teacher + students + room) | *This week* → click a class → *Find a makeup time* (or a cancelled class → *Find a makeup class*) |
| Attendance of every section, students below the rule first; set the rule (e.g. 75%) | **Attendance** |
| Undo the last change, see who changed what | **Activity** (sidebar) |
| Excel / PDF for notice boards (one or all sections / teachers / rooms) | **Timetable** → *Download* |
| Setup wizard: days, lab length, 1 or 2 shifts, periods, breaks, lunch window, holidays, semester dates, departments, rooms | **College setup** |
| Department data, Excel import, teacher suggestions, Ready status | **Departments** → pick one |
| College / department rules (Must / Try) | **Rules** |
| Invite Coordinators and teachers | **People & invites** |
| Approve teachers' requests to move a class | **Change requests** |
| Read everything the college has entered | **College data** |
| Find a time when chosen teachers are all free → book a meeting | **Meetings** |

### Department Coordinator (CSE)

| Feature | Where |
|---|---|
| Department workspace: sections, subjects, teachers, who teaches what | **My department** |
| Excel: download the sheet (already filled), fill it, upload it → row-level errors | **My department** → *Download sheet* / *Upload filled sheet* |
| Teacher allotment suggestions with reasons → approve | **My department** → *Suggest for empty* / *Re-suggest all* |
| Mark the department Ready for the Admin | **My department** → *Mark department Ready* |
| One list of every student in a year → sections + lab batches automatically (by roll number or mixed by hostel, etc.) | **My department** → *Make sections from a whole-year list* |
| Move or change own department's classes | **Timetable** (same as Admin, own department only) |
| Teachers' change requests → *Review and approve* / *Decline* | **Change requests** (dashboard shows a banner when some wait) |
| Own sections' attendance, below-rule students first | **Attendance** |
| Department rules | **Rules** |
| Meeting with own department's teachers at a common free time | **Meetings** |

### Teacher (sees only their own lectures)

| Feature | Where |
|---|---|
| **Today**: now / next class with room and countdown, finished classes greyed | **My timetable** → *Today* |
| **Take attendance** (everyone present by default, tap the absent) | *Today* → *Take attendance*, or **Attendance** (last 7 days) |
| Makeup time for a cancelled lecture | *This week* → click the lecture → *Find a makeup class* |
| My timetable on real dates | **My timetable** → *This week* |
| Cancel or move my lecture for one day (instant, students notified) | **My timetable** → *This week* → click a lecture |
| Ask the Coordinator to move a lecture permanently | **My timetable** → *Weekly plan* → click a lecture → click a slot → reason → *Send request* |
| Follow my requests (waiting / approved / declined) | **My requests** |
| Times I can't teach (confirmed instantly if no clash) | **My availability** |
| Download my timetable | **My timetable** → *Download* |
| Weekly office hours for doubt slots; see who booked | **Bookings** |

### Student (sees only their own classes)

| Feature | Where |
|---|---|
| **Today**: next class in N minutes, in which room; lunch | **My timetable** → *Today* |
| My week, including cancellations and moves | **My timetable** → *This week* / *Weekly plan* |
| **My attendance**: overall + per subject vs 75%, "you can miss N more" | **My attendance** |
| Download / print my timetable | **My timetable** → *Download* / *Print* |
| "When am I free next week?", "What's my attendance?", "Which room is free?" | **Ask** (Ctrl+K) |
| Changes to my classes | the **bell** |
| Book a doubt slot with a teacher (only times when I have no class) | **Bookings**, or Ask: "Anita ma'am ke saath doubt slot book karna hai" |

## 4. A 6-minute demo script (for the video)

1. **Login** → *Try the demo college* → **College Admin**. Dashboard: next step, 0 clashes, quality score,
   every department Ready.
2. **Timetable** → CSE-2A: lunch sits at a different time each day (chosen per section, inside the mess
   window). Switch to *Teacher* and *Room* views: same timetable, three angles.
3. Drag a class → green / amber / red slots → drop on amber → the review lists exactly which classes move,
   "Checked: no clashes" → **Apply** → **Activity** → **Undo**.
4. *This week* → click a class → **Cancel** for a date with a reason → click it again → **Find a makeup
   class** → pick the first time → book. Log in as a **Student** of that section → the bell shows both.
5. **Teacher** → *Today* / **Attendance** → open a class → tap two absent students → Save. **Student** →
   **My attendance**: percentage, the 75% rule, "attend the next N classes".
6. **Teacher** → *Weekly plan* → ask to move a lecture → **Coordinator** (dashboard banner) → Change
   requests → Review → Apply → the teacher gets "approved".
7. **Ask** (Ctrl+K): Admin "Who is below 75% attendance in CSE-1A?", "Move CSE-2B's Monday DBMS lecture to
   Friday morning" (card → Apply). Student "What's my attendance, and can I miss a class?".
8. **Download** → PDF of all sections. Toggle light / dark. Show it on a phone width.
9. **Sign up** a new college → setup wizard (1 or 2 shifts, mess window) or *Load sample college* → Generate.

Key message: the timetable is built by an algorithm (Google OR-Tools CP-SAT) and every timetable and every
change is checked by an independent validator, so no clash ever reaches anyone. The AI assistant only
answers and proposes; a person always clicks Apply.
