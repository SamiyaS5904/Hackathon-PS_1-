# GNDEC (demo): load it into Timetabl.ai yourself

Tested on a local copy, 2026-10-27, in exactly these steps: every file uploads with **0 errors**, the
pre-check is clean, and Generate gives **0 clashes** (557 classes; quality about 65 with the normal 45-60 s,
higher if you let it run longer).

## 1. Sign up a new college
Name it e.g. **Guru Nanak Dev Engineering College (demo)**. You become its College Admin.

## 2. Setup (College Admin)
| Field | Value |
|---|---|
| Shifts | **1 shift**, name **Day** |
| Periods | 9 periods of **60 minutes**, first one at **08:30** (08:30-09:30 ... 16:30-17:30), no fixed breaks |
| Lunch (mess window) | **11:30 to 13:30** (every section gets one free hour in it, every day) |
| Lab length | **2 periods** |
| Working days | Mon to Fri |
| Holidays | 24 Nov 2026: Guru Nanak Dev Ji Gurpurab |
| Semester | 5 Aug 2026 to 4 Dec 2026 |
| Departments (short name **exactly** as below) | **CSE** Computer Science and Engineering · **IT** Information Technology · **ME** Mechanical Engineering · **CE** Civil Engineering · **AS** Applied Sciences |
| Shared rooms (optional) | WS Seminar Hall, Seminar, 200 seats (for event bookings) |

The shift name must be **Day** and the short names exactly **CSE, IT, ME, CE, AS**: the files use them.

## 3. Upload the department files, in this order
On each department's page: *Upload Excel* → check the preview → *Save*.
1. `GNDEC_1_AS.xlsx` (Applied Sciences: first-year teachers, subjects, lecture theatres, drawing halls, workshops)
2. `GNDEC_2_CSE.xlsx` (11 sections, 652 students)
3. `GNDEC_3_IT.xlsx` (7 sections, 414 students)
4. `GNDEC_4_ME.xlsx` (5 sections, 298 students)
5. `GNDEC_5_CE.xlsx` (5 sections, 298 students)

Applied Sciences must go first: the other files name its teachers and subjects for first-year classes.

## 4. Generate and publish
Mark CSE, IT, ME and CE **Ready** (Applied Sciences has no sections of its own, so it can't be marked Ready;
that doesn't stop Generate). Then *Generate* → check 0 clashes → *Publish*.

## What's inside
28 sections (D1-D4 of CSE, IT, ME, CE, two lab groups each, e.g. D2CS-A = A1 + A2), 1,662 students,
96 teachers (made-up names), 51 rooms and labs (CSE / IT names follow GNDEC: G-12, S-213, Software Lab-I..IV,
DBMS / OS / PL / HW / WD / HPC labs), first-year maths for D1CS-A + D1CS-B together in a lecture theatre, and
2+ teachers who can teach almost every subject (so leave cover finds a substitute).

Student logins: their email (`<roll no>@gndec.demo`, e.g. `2515001@gndec.demo`), first password = roll number.
Teachers and Coordinators: invite them from *People & invites*.

Not in the files (they need a student list per group): the final-year CSE **JPAL hour** and the **department
elective**. They are in the built-in GNDEC college (`backend/app/seed/gndec.py`) and can be added in Setup.

`Timetabl_blank_template.xlsx` is the same format with headings only and a *Read me* sheet, for any college.
