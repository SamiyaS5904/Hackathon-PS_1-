# PIET (sample): create a college from scratch

A ready dataset for showing how a new college is set up in Timetabl.ai: sign up, Setup, upload the department
files, Generate. The data matches the GNDEC sample (same sections, subjects, teachers and rooms) under the name
**Panipat Institute of Engineering and Technology (PIET)**. Student logins use `@piet.test`, so this college never
shares accounts with the built-in demo colleges. Regenerate the files with `python -m app.seed.piet` (in `backend/`).

## Quick version (for a demo video): 2 departments, about 5 minutes

Tested end to end: 11 sections, 652 students, **208 classes, 0 clashes**, Generate in about 45 s.

1. **Sign up** (*Get started free*): college name **Panipat Institute of Engineering and Technology**, your own
   email and password. You become its College Admin.
2. **Setup**:
   - *Week & labs*: Mon to Fri, lab length **2 periods**.
   - *Timings*: **1 shift** named **Day**, **9 periods of 60 minutes** from **08:30**, no fixed breaks,
     mess window **11:30 to 13:30**.
   - *Calendar*: holidays and semester dates are optional.
   - *Departments*: short name **CSE** = Computer Science and Engineering, **AS** = Applied Sciences
     (short names exactly so: the files use them).
3. **Upload**, in this order (department page → *Upload filled sheet* → check → *Save*):
   `PIET_1_AS.xlsx` in Applied Sciences, then `PIET_2_CSE.xlsx` in CSE. Expect 0 errors. A grey note
   "No classes to schedule yet" on the first file is normal (Applied Sciences has no sections of its own).
4. **Mark CSE Ready** (Applied Sciences has no sections, so it doesn't need it).
5. **Generate** → check **0 clashes** → **Publish**.
6. **Invite a teacher**: *More → People & invites* → e.g. `teacher.one@piet.test`, role Teacher, department CSE →
   copy the invite link.

Student logins: `<roll no>@piet.test` (e.g. `2515001@piet.test`), first password = roll number.

## Full version: 5 departments

Add **IT** Information Technology, **ME** Mechanical Engineering and **CE** Civil Engineering in Setup, and upload
`PIET_3_IT.xlsx`, `PIET_4_ME.xlsx`, `PIET_5_CE.xlsx` too: 28 sections, 1,662 students, 96 teachers, 557 classes,
0 clashes. This size needs a few solver workers: about 64 s with 4 workers; a single small CPU may not find a
timetable in the 45 s the Generate button allows.
