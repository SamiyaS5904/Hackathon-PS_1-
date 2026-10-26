# GNDEC (demo): assistant test scenarios

Real-life questions for the assistant on the GNDEC demo college (`backend/app/seed/gndec.py`), per role,
with what a good answer must contain. Every account's password is `demo1234`.

**Pass criteria for every answer:** correct for *this* login only (a student never sees another section, a
teacher only their own lectures, a Coordinator only their department); times and rooms match the published
timetable; any change comes as a card with **Apply** (never applied by the assistant itself); short and plain
(no "session", "allotment", "constraint"); same language as the question (English, or Roman Hinglish).

College facts the answers rely on: Mon-Fri, nine 1-hour periods 08:30-17:30; every section has one free
period between 11:30 and 13:30 for lunch, every day (about half the students eat at 11:30, half at 12:30);
2 lab groups per section (e.g. A1 / A2); final-year CSE has a Department Elective (Computer Vision / Data
Warehousing and Data Mining / Software Defined Networks) and the **JPAL hour**: about 30 selected D4 CSE
students go to the **JPAL Lab**, everyone else in D4 CSE has a Major Project Review with their section's guide
at the same hour. Holiday: Tue 24 Nov 2026 (Guru Nanak Dev Ji Gurpurab).

## Logins used

| Role | Login | Notes |
|---|---|---|
| College Admin | admin@gndec.demo | everything |
| Coordinator | cse.coordinator@gndec.demo (also it., me., ce., as.) | own department |
| Teacher | varun.chopra@gndec.demo (CSE, Data Structures, D2CS) · harleen.grewal@gndec.demo (AS, first-year maths) | own lectures |
| Student | 2515001@gndec.demo (D2CS-A) · 2315001@gndec.demo (D4CS-A, not in JPAL) · 2315004@gndec.demo (D4CS-A, **JPAL**) · 2611001@gndec.demo (D1CE-A) | own section / groups |

## Student (read-only)

| # | Question | A good answer contains |
|---|---|---|
| 1 | Where can I sit now? I have a free lecture. | Rooms free right now (no class, no event), with seats and how long each stays free; nearby own-department rooms first. Never a lab in use. |
| 2 | What's my next class? | Subject, time, room, teacher; "no more classes today" after the last one; holiday on 24 Nov. |
| 3 | Do I have any gaps tomorrow? | Tomorrow's classes in order with the free periods between them named (lunch shown as lunch, not as a gap). |
| 4 | When is my JPAL lab? (JPAL student) | Day and hour of the JPAL hour, JPAL Lab, teacher. |
| 5 | When is my JPAL lab? (D4CS-A student not in JPAL) | "You are not in the JPAL group"; at that hour you have Major Project Review with your guide, in room X. |
| 6 | Which elective group am I in and when does it meet? (D4 CSE) | The student's own group (one of the three), its 3 meetings a week, room, teacher. |
| 7 | When is lunch today? | The student's own free period in the mess window today (it can differ by day). |
| 8 | Where is Dr. Varun Chopra right now? | Teaching / free / not in college, with room if teaching; nothing about other students. |
| 9 | Show my timetable for Thursday. | Thursday only, own section and lab group (A1 vs A2 labs differ). |
| 10 | Is there college on 24 November? | No: Guru Nanak Dev Ji Gurpurab (holiday). |
| 11 | Mera Data Structures lab kab hai? (D2CS-A, Roman Hinglish) | Reply in Roman Hinglish: own lab group's DS lab day, time, lab name. |
| 12 | Book a doubt slot with my maths teacher this week. | Open office-hour slots (if the teacher set any) as a card to book; or "no office hours yet". |
| 13 | What's my attendance in Engineering Physics? (D1CE-A) | Percentage vs the 75% rule, how many classes can be missed / must be attended. |
| 14 | Move my DS class to Friday. | Polite no: students can't change the timetable; suggest asking the teacher. |
| 15 | Show D3CS-B's timetable. (D2CS-A student) | Refuses other sections' details (own timetable only). |
| 16 | Which rooms are free from 2:30 to 4:30 for group study? | Rooms free for the whole window, with seats. |

## Teacher

| # | Question | A good answer contains |
|---|---|---|
| 1 | What do I teach tomorrow? | Own lectures and labs only: time, section (+ lab group), room. |
| 2 | When am I free on Wednesday? | Free periods (and lunch window) with no class. |
| 3 | I can't take Thursday's 10:30 class. Find a makeup time this week. | Times when the teacher, every student of that section and a room are free; a card to move it for one day; students notified on Apply. |
| 4 | Cancel my 3:30 class tomorrow, I have a meeting. | One-day cancel card (reason), Apply; students told. |
| 5 | Move my Monday DS lecture to Friday 11:30 every week. | A request to the CSE Coordinator (permanent change needs approval), only if that slot is free every week. |
| 6 | I'm on leave next Monday and Tuesday. | A leave request to the Coordinator, listing the classes affected. |
| 7 | Who has booked my office hours this week? | Own doubt-slot bookings only. |
| 8 | Which room can I take for a remedial class at 2:30 today? | Free rooms big enough for the section (60), for that hour. |
| 9 | Show D2CS-B timetable (a section the teacher teaches). | Allowed only for own lectures; otherwise a polite limit. |
| 10 | Kal mere kitne lecture hain? (Roman Hinglish) | Count + list, in Roman Hinglish. |
| 11 | Book the WS Seminar Hall for a coding contest on Friday 2:30-4:30. | Free-room check; booking request goes to the College Admin (shared hall); never bumps a class. |
| 12 | How many students in D2CS-A are below 75% attendance? (own class) | Numbers for own classes only. |
| 13 | Undo that. (after a one-day change) | Undoes the teacher's own last change, or explains what can be undone. |
| 14 | When is the JPAL hour? (JPAL teacher) | Day, hour, JPAL Lab, ~30 students. |
| 15 | Which subjects can I also teach? | Own "can teach" list (1st and 2nd choices). |

## Department Coordinator (CSE)

| # | Question | A good answer contains |
|---|---|---|
| 1 | Prof. Varun Chopra is on leave Mon and Tue next week; plan cover. | Leave plan card per class: a substitute who can teach Data Structures (e.g. the 2nd teacher of DS, free then, within the daily limit) or cancel; Apply; students + teachers notified. |
| 2 | Free the 4th-year lectures, substitutes for 2nd year. | Plan honours the per-year choice. |
| 3 | Find a makeup time for D3CS-B's cancelled Cyber Security class. | Times in the next 7 days with teacher, all students and a room free; a card. |
| 4 | Move D2CS-C Computer Architecture from Tuesday to Thursday. | A proposal with a before/after diff; other classes moved only if needed; validator OK; Apply. |
| 5 | Which CSE classes have no teacher? | None in the demo; otherwise a list with suggestions. |
| 6 | Who teaches Design and Analysis of Algorithms, and who can cover it? | The 2 teachers + the 2nd-choice teacher. |
| 7 | Where do D4 CSE students sit during the JPAL hour if they're not in JPAL? | Major Project Review rooms per section (they are not free). |
| 8 | Which CSE rooms are free on Friday afternoon? | Own and shared rooms free then. |
| 9 | Find a 1-hour meeting time with Dr. Rupinder Virk and Prof. Parminder Sood this week. | Times when both are free; a meeting card. |
| 10 | Approve the room request for the Robotics demo. | Only requests for CSE rooms; approve / decline with a note. |
| 11 | How many gaps do D4 CSE students have? | Per section, gaps per day; suggestions if many. |
| 12 | Post a notice for 3rd year: project review Friday 2 pm. | A notice for CSE year 3 (bell + Home), with an expiry date. |
| 13 | Show ME department's timetable. | Allowed to view? Only own department + shared rooms; ME details refused or limited. |
| 14 | Tomorrow's brief. | Leaves, uncovered classes, room requests waiting, "fix them?" |
| 15 | Undo the last change. | Undo of own last change (activity log). |
| 16 | Kal CSE mein kaun kaun chutti pe hai? | Roman Hinglish list of teachers away tomorrow and their classes. |

## College Admin

| # | Question | A good answer contains |
|---|---|---|
| 1 | Is the timetable clash-free? What's the quality score? | 0 clashes (independent check), the score and its main penalties (gaps, week balance, room fit). |
| 2 | Which departments are ready? | All 5 Ready (built-in demo). |
| 3 | Why is D1CS-A's maths in a lecture theatre? | Combined class D1CS-A + D1CS-B, 118 students: only LT-1 / LT-2 (and the seminar hall) have enough seats. |
| 4 | How is lunch spread across the mess? | About half the students at 11:30, half at 12:30, every day (mess split rule on). |
| 5 | Which rooms are least used? | Utilisation per room, idle rooms named. |
| 6 | Move all D4 CSE electives to Wednesday morning. | Explains elective groups move together; proposal only if all groups, teachers and rooms are free. |
| 7 | Dr. Harleen Grewal (first-year maths) is away all week; plan cover. | Same-subject substitutes from Applied Sciences ranked; cancel where none. |
| 8 | Which teachers have more than 4 classes on a day? | Names, days, counts. |
| 9 | Show the Software Lab-I timetable. | Room view for that lab. |
| 10 | Book the WS Seminar Hall for the Annual Tech Fest on 20 Nov, 1:30-5:30. | Booked straight away (Admin looks after shared halls) if free; the hall is held for that date. |
| 11 | Post a notice to everyone: college closed on 24 Nov for Gurpurab. | A college-wide notice + bell. |
| 12 | How many students are below 75% attendance? | Per department / section, below-rule students first. |
| 13 | What does the assistant cost us this month? | Token use and cost for this college. |
| 14 | Regenerate keeping the current timetable. | Explains minimal-change regenerate (only classes that must move do). |
| 15 | Publish the timetable. | Asks to confirm; then teachers and students see it and are notified. |

## How to run them

1. Load the college locally (SQLite, not the shared database) with
   `build_gndec_college()` + `app.accounts.seed_accounts("gndec", college, "gndec.demo")`, generate once
   (`time_limit=180` gives quality about 77; 60 s about 66) and publish.
2. Start the backend and the assistant on spare ports, log in with the accounts above and ask each question
   in the chat panel (type it, then once by voice).
3. Mark each row pass / fail against "A good answer contains", and note the time to the first word.

## Results (local run, 2026-10-27)

Local copy (SQLite, backend on port 8100), GNDEC generated with `time_limit=180` and 2 solver workers:
**570 classes, 0 clashes, quality 79** (gaps penalty 1.1: 10 idle periods across 56 lab groups a week; no day
with a single class). Questions were asked through the assistant's own tools and instant answers (same
permissions as the chat, no AI model, so no cost), as of Wed 28 Oct 10:45. The model-written answers
(leave wording, Hinglish, proposals) still need a run in the chat panel with an API key.

| Role | Question | Result | Time |
|---|---|---|---|
| Student D2CS-A | Where can I sit now? | Pass: "25 rooms are free right now", seats and until when. *Improve:* labs (JPAL Lab, Drawing Hall, SOM Lab) are listed before lecture rooms; for "where can I sit" lecture rooms of the own department should come first. | 0.16 s |
| Student D2CS-A | What's my next class? | Pass: current class (OOP, S-215, until 11:30) and the next one with teacher and room. | 0.02 s |
| Student D2CS-A | What do I have tomorrow? | Pass: 4 classes with times, rooms, teachers. | <0.01 s |
| Student D2CS-A | Gaps tomorrow? | Pass: free 08:30-10:30 and 12:30-13:30, lunch 11:30-12:30 shown as lunch. | 0.08 s |
| Student D2CS-A | Show D3CS-B's timetable | Pass: refused (students see only their own). | - |
| Student D2CS-A | College on 24 Nov? | Pass: no classes, "Guru Nanak Dev Ji Gurpurab". | 0.01 s |
| Student D4CS-A (JPAL) | When is my JPAL lab? | Pass: Mon 10:30-11:30, JPAL Lab, the JPAL teacher. | - |
| Student D4CS-A (not JPAL) | When is my JPAL lab? | Pass (data): their week shows Major Project Review at that hour, not JPAL. | - |
| Teacher (CSE) | What do I teach tomorrow? | Pass: own 2 classes only (D2CS-A lecture, D2CS-B B2 lab). | 0.03 s |
| Teacher (CSE) | When am I free on Thursday? | Pass: 08:30-10:30, 11:30-13:30, 15:30-17:30. | 0.07 s |
| Teacher (CSE) | Rooms for 60 at 14:30 | Pass: only rooms with 60+ seats, with owner department. | 0.01 s |
| CSE Coordinator | Teacher on leave Mon-Tue: plan cover | Pass: 4 classes, all 4 covered by the second Data Structures teacher (same subject), within daily limits; nothing changes until Apply. | 0.46 s |
| CSE Coordinator | Show D2CS-C timetable | Pass: opens it. | <0.01 s |
| ME Coordinator | Show D2CS-A timetable (CSE) | Opens it: Coordinators can view every department's timetable today (they edit only their own). Matches the app; check against the roles table if view should be limited. | 0.11 s |
| College Admin | Clash-free? Quality? | Pass: score 79 with each penalty explained. | 0.13 s |
| College Admin | Which departments are ready? | Pass: all 5 Ready, with sections / teachers / classes / students. | 0.01 s |
