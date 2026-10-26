# Timetabl.ai: run it, log in, find every feature, give the demo

## 1. Open it

- **Live site:** the Vercel address (see the README). Nothing to install.
- **On this laptop:** double-click **`start-local.bat`** in `D:\Hackathon`. Three windows open (backend, assistant,
  web app); the first start takes 1-2 minutes; the browser opens http://localhost:3000. Close the three
  "Timetabl" windows to stop.

> Use either the live site or the local app during the demo, not both at once: they share one database.

The address opens the **home page**: the problem, features, the AI assistant, how it works, roles and pricing.
Click **Try the demo**.

## 2. Log in (password for every demo account: `demo1234`)

| Choice on the Demo page | Who | Email |
|---|---|---|
| College Admin | runs the whole college | `admin@demo.timetabl.ai` |
| Department Coordinator | pick CSE, ECE, ME or Applied Sciences | `cse.coordinator@demo.timetabl.ai` |
| Teacher | Dr. Anita Sharma | `anita.sharma@demo.timetabl.ai` |
| Student | pick a section, roll 01 | `cse3a.01@demo.timetabl.ai` |
| Platform owner (SaaS) | every college: stage, health, plans, pause | `owner@demo.timetabl.ai` |

Any student works by hand (`ece2a.12@demo.timetabl.ai`: section + roll 01-60). Switch user with the log-out icon.

Everywhere:
- **sun / moon** = light / dark
- **bell** = notifications
- **Ask** or **Ctrl+K** = the AI assistant

## 3. The AI assistant

- **Chat**: type, or tap the mic and speak. Your words appear in the box as you talk, and pauses are fine. Tap
  **Done**, check or edit the text, then send.
- **Talk**: hands-free. Speak and pause: it answers aloud while the answer is still coming. Talk over it to
  interrupt. Say **"stop"** to quiet it, **"bye"** to end.
- **Replies in English** by default; switch to **Hinglish** at the top of the panel.
- **Instant answers** (marked ⚡, under a second, no AI cost):
  - "What's my next class?", "What do I have tomorrow?"
  - "Which rooms are free right now?", "Where is Dr. Neha Arora?"
  - "Show CSE-3A timetable", "Open bookings", "Undo", "My attendance"
- **Agentic requests** become cards you Apply:
  - "Dr. Harpreet Kaur is away tomorrow, plan cover": a cover plan.
  - "Move CSE-2A's Monday Data Structures lecture to another day": a checked move.
  - "Cancel CSE-2B's Data Structures lab on Thursday and find a makeup time": a one-day move.
  - "Find a meeting time this week for Dr. Neha Arora and Prof. Rohit Bansal": a meeting.
- **It drives the screen**: the timetable, teacher, week or page it talks about opens beside the chat.
- **Typing suggestions** use the college's real names; press **Tab** to take the first one.

## 4. Where each feature is

### College Admin

| Feature | Where |
|---|---|
| Next step, today (teachers away, changes, requests), setup checklist | **Home** |
| Tomorrow's brief: leave without cover, *Plan cover*, *Brief me* | **Home** → *Tomorrow* |
| Teacher leave waiting / covered | **Home** → *Teacher leave* |
| Assistant cost (today, 7 days, month, per answer) | **Home** → *Assistant cost* |
| Generate / Regenerate (*Keep the current timetable* moves as few classes as possible) / Publish | **Timetable** |
| Section, teacher, room views; drag and drop (green / amber / red) → review → Apply | **Timetable** → *Weekly plan* |
| One-day cancel / move; makeup finder | **Timetable** → *This week* → click a class |
| A teacher is away → cover plan (substitutes ranked, per year cancel or cover) | **Home** → *Teacher away* |
| Every change, Undo, requests waiting | **Changes** |
| Setup wizard (shifts, periods, mess timings, holidays, departments, rooms) | **Setup** |
| Department data, Excel upload with errors marked, teacher suggestions, Ready | **More** → *Departments* |
| Attendance per section, the college's minimum | **More** → *Attendance* |
| Meetings when chosen teachers are all free | **More** → *Meetings* |
| Room requests for events (approve shared rooms) | **More** → *Room booking* |
| Rules (Must / Try, incl. mess split), people and invites, college data | **More** |
| Notices to a department, a year or a section | **Home** → *Notices* → *New notice* |
| Excel / PDF exports | **Timetable** → *Download* |

### Department Coordinator

| Feature | Where |
|---|---|
| Approve a teacher's leave → plan cover → Apply | **Home** → *Teacher leave* |
| Tomorrow's brief | **Home** → *Tomorrow* |
| Own department's data, Excel, suggestions, Ready | **My department** |
| Move / change own department's classes | **Timetable** |
| Teachers' requests, changes, Undo | **Changes** |
| Approve room requests for own department's rooms | **More** → *Room booking* |
| Notices to own teachers / students / a year / a section | **Home** → *Notices* |

### Teacher (sees only their own lectures)

| Feature | Where |
|---|---|
| Today and this week; covered classes show "Covered by …", substitutes see "You're covering" | **Home** |
| Ask for leave | **Home** → *My leave* → *Ask for leave* |
| Take attendance | **Home** (Today) or **More** → *Attendance* |
| Reschedule: when you, your students and a room are all free → move for one day or ask for good | **Timetable** → click a lecture |
| Office hours and who booked them | **Bookings** |
| Book a room for a club event (free rooms only) | **More** → *Room booking* |

### Student (sees only their own classes)

| Feature | Where |
|---|---|
| Today (next class, room, countdown, lunch) and the week with changes | **Home** |
| Attendance vs the minimum, "you can miss N more" | **More** → *My attendance* |
| Book a doubt slot (only when you have no class) | **Bookings** |
| "Where can I sit now?" (free rooms), "Where is Dr. …?" | **Ask** |

## 5. A 7-minute demo script

1. **Home page** (30 s): the problem, "0 clashes", the assistant, pricing. Click **Try the demo** → **College Admin**.
2. **Timetable** (1 min):
   - CSE-2A: every section gets lunch inside the mess timings, at a different time per day.
   - Switch to the Teacher and Room views.
   - Drag a class: green / amber / red slots. Drop it on amber; the review says what moves and "0 clashes". Apply,
     then Undo.
3. **Teacher leave** (1.5 min): log in as **Coordinator** → Home → **Teacher away**.
   - Pick Dr. Harpreet Kaur and tomorrow. Each class gets a substitute with the reason ("same department, free then,
     knows this class").
   - Switch one year to **Cancel**, then **Apply**.
   - Log in as a **student** of that section: the class shows the substitute and the bell has the notice.
4. **Assistant, Talk mode** (1.5 min): **Ctrl+K** → **Talk**. Say:
   - "Which rooms are free right now?": instant answer, spoken.
   - "Show Prof. Rohit Bansal's timetable": it opens on screen.
   - "Find a meeting time this week for Dr. Neha Arora and Prof. Rohit Bansal": card → **Book**.
   - "Undo": Undo card.
5. **Teacher** (1 min): Ask for leave, take attendance in two taps, book a room for a club event (the
   Coordinator approves it).
6. **Student** (30 s): Today on a phone width, attendance, "What's my next class?" (instant).
7. **Admin** (30 s): Home → **Assistant cost** (₹ per answer). Platform owner: every college's health.

**Key message:** the timetable is built by an algorithm and every timetable and every change is checked by an
independent validator, so no clash ever reaches anyone. The AI assistant plans and prepares; a person always
clicks Apply, and it can never do more than that person could.
